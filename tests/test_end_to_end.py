import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from mock_folio import MockFolio, U, default_data
from pymarc import MARCReader

from folio_chq import client as client_mod
from folio_chq.cli import main


def _recent(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def folio():
    data = default_data()
    for loan in data["loans"]:
        if loan.get("loanDate") == "RECENT":
            loan["loanDate"] = _recent(30)
        if loan.get("returnDate") == "RECENT_RETURN":
            loan["returnDate"] = _recent(10)
    with MockFolio(data) as m:
        yield m


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)


def write_config(tmp_path: Path, url: str, **overrides) -> Path:
    cfg = {
        "folio": {"base_url": url, "tenant": "diku", "username": "chq", "password": "secret", "page_size": 2},
        "extract": {"cache_path": str(tmp_path / "cache.sqlite"), "exclude_location_codes": ["ONLINE"]},
        "legacy": {"circ_count_note_type": "Legacy circ count", "created_date_note_type": "Legacy created date"},
        "output": {"directory": str(tmp_path / "out"), "file_prefix": "test"},
        "delivery": {"method": "local"},
    }
    for section, values in overrides.items():
        cfg.setdefault(section, {}).update(values)
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def latest_run(tmp_path):
    return sorted((tmp_path / "out").glob("2*"))[-1]


def read_outputs(run_dir):
    mrc = next(run_dir.glob("*.mrc"))
    with open(mrc, "rb") as fh:
        records = list(MARCReader(fh, to_unicode=True, force_utf8=True))
    with open(next(run_dir.glob("*.csv")), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return records, rows


def test_full_run_outputs(tmp_path, folio):
    cfg = write_config(tmp_path, folio.url)
    assert main(["-c", str(cfg), "run"]) == 0
    run = latest_run(tmp_path)
    report = json.loads((run / "run-report.json").read_text())
    assert report["status"] == "success"
    records, rows = read_outputs(run)

    # Bibs: in1 (SRS) and in2 (generated). in3 suppressed, in4 only has an ONLINE item, in5 has no items.
    by_001 = {r["001"].data: r for r in records}
    assert set(by_001) == {"in00000000001", "in00000000002"}
    r1 = by_001["in00000000001"]
    assert r1["245"]["a"] == "Learning Python /"
    f949 = r1.get_fields("949")
    assert [f["a"] for f in f949] == ["B0001", "B0002"]          # old local 949 stripped; suppressed item excluded
    assert f949[0]["l"] == "MAIN-STACKS" and f949[0]["c"] == "QA76.73.P98 L88 2020"
    r2 = by_001["in00000000002"]
    assert r2["245"]["a"] == "A FOLIO-only record"
    assert r2["100"]["a"] == "Doe, Jane"
    assert r2["020"]["a"] == "9781234567897"
    assert r2["050"]["a"] == "Z678.9 .D64 2019"
    assert r2["999"]["i"] == U(2)
    assert r2.leader[9] == "a"

    # Items: linked to bibs by instance HRID; every barcode also appears in the bib's 949.
    bcs = {row["Barcode"]: row for row in rows}
    assert set(bcs) == {"B0001", "B0002", "B0003", "B0005", ""}  # Withdrawn kept (status is reported), no-barcode kept
    assert bcs["B0005"]["Status"] == "Withdrawn"
    assert {row["Instance HRID"] for row in rows} <= set(by_001)
    marc_barcodes = {f.get("a") for r in records for f in r.get_fields("949") if f.get("a")}
    assert marc_barcodes == {b for b in bcs if b}

    b1 = bcs["B0001"]
    assert b1["Total Checkouts"] == "2"
    assert b1["Checkouts Last 12 Months"] == "1"
    assert b1["Last Circ Date"] == _recent(30)[:10]
    assert b1["Last Checkin Date"] == "2025-02-01"
    assert b1["Material Type"] == "book" and b1["Library"] == "Main Library"
    assert b1["Call Number Type"] == "Library of Congress classification"

    b2 = bcs["B0002"]
    assert b2["Status"] == "Checked out" and b2["Due Date"] == "2099-01-01"

    b3 = bcs["B0003"]
    assert b3["Total Checkouts"] == "43"                         # 1 FOLIO loan + 42 legacy
    assert b3["Created Date"] == "1998-03-15"                    # legacy note wins over migration date
    assert b3["Call Number"] == "DVD PN1997 .X1"
    assert b3["Location"] == "Science Library Stacks"

    assert report["build"]["items_without_barcode"] == 1
    assert report["build"]["bibs_generated"] == 1
    assert report["build"]["items_skipped"]["location excluded"] == 1
    assert report["build"]["items_skipped"]["instance suppressed"] == 1


def test_delta_picks_up_changes_and_deletions(tmp_path, folio):
    cfg = write_config(tmp_path, folio.url)
    assert main(["-c", str(cfg), "run"]) == 0

    # Change an item's status, and delete another item.
    later = _recent(0).replace("Z", ".000+00:00")
    it = next(i for i in folio.data["items"] if i["barcode"] == "B0001")
    it["status"] = {"name": "Missing", "date": later}
    it["metadata"]["updatedDate"] = later
    folio.data["items"] = [i for i in folio.data["items"] if i["barcode"] != "B0002"]
    folio.requests.clear()

    assert main(["-c", str(cfg), "run", "--force"]) == 0
    report = json.loads((latest_run(tmp_path) / "run-report.json").read_text())
    assert report["sync"]["mode"]["instances"] == "delta"
    assert report["sync"]["mode"]["items"] == "full"             # deletion detected -> full resync
    _, rows = read_outputs(latest_run(tmp_path))
    bcs = {r["Barcode"]: r for r in rows}
    assert bcs["B0001"]["Status"] == "Missing"
    assert "B0002" not in bcs


def test_safety_check_blocks_delivery(tmp_path, folio):
    cfg = write_config(tmp_path, folio.url)
    assert main(["-c", str(cfg), "run"]) == 0
    folio.data["items"] = folio.data["items"][:1]
    assert main(["-c", str(cfg), "run"]) == 2
    report = json.loads((latest_run(tmp_path) / "run-report.json").read_text())
    assert report["status"] == "blocked"


def test_retries_and_relogin(tmp_path, folio):
    cfg = write_config(tmp_path, folio.url)
    folio.fail_next = [503, 502]
    assert main(["-c", str(cfg), "sync"]) == 0
    folio.expire_tokens = True                                   # server rejects old token -> client logs in again
    assert main(["-c", str(cfg), "run", "--skip-sync", "--no-deliver"]) == 0
    assert main(["-c", str(cfg), "check"]) == 0


def test_bad_password(tmp_path, folio):
    cfg = write_config(tmp_path, folio.url, folio={"password": "wrong"})
    assert main(["-c", str(cfg), "run"]) == 1


def test_split_and_custom_columns(tmp_path, folio):
    cfg = write_config(
        tmp_path, folio.url,
        output={"directory": str(tmp_path / "out"), "file_prefix": "t",
                "marc": {"split_every": 1},
                "items_csv": {"delimiter": "|", "date_format": "%d/%m/%Y",
                              "columns": [{"header": "BARCODE", "field": "barcode"},
                                          {"header": "BIBID", "field": "instance_hrid"},
                                          {"header": "CREATED", "field": "created_date"}]}},
        extract={"cache_path": str(tmp_path / "c.sqlite"), "include_items_without_barcode": False,
                 "exclude_item_statuses": ["Withdrawn"], "bibs_without_items": True},
    )
    assert main(["-c", str(cfg), "run"]) == 0
    run = latest_run(tmp_path)
    assert len(list(run.glob("*.mrc"))) == 4                     # in1, in2, in4 (no eligible items), in5
    lines = next(run.glob("*.csv")).read_text().splitlines()
    assert lines[0] == "BARCODE|BIBID|CREATED"
    assert "B0003|in00000000002|15/03/1998" in lines
    assert not any(line.startswith("|") for line in lines)       # no-barcode item dropped


def test_deliver_refuses_failed_run(tmp_path, folio):
    cfg = write_config(tmp_path, folio.url)
    assert main(["-c", str(cfg), "run", "--no-deliver"]) == 0
    run = latest_run(tmp_path)
    rep = json.loads((run / "run-report.json").read_text())
    rep["status"] = "failed"
    rep.pop("build")
    (run / "run-report.json").write_text(json.dumps(rep))
    assert main(["-c", str(cfg), "deliver"]) == 2


def test_instance_switching_to_folio_source_drops_stale_marc(tmp_path, folio):
    cfg = write_config(tmp_path, folio.url)
    assert main(["-c", str(cfg), "run"]) == 0
    inst = next(i for i in folio.data["instances"] if i["hrid"] == "in00000000001")
    inst["source"] = "FOLIO"
    inst["title"] = "Now FOLIO-sourced"
    inst["metadata"]["updatedDate"] = _recent(0).replace("Z", ".000+00:00")
    assert main(["-c", str(cfg), "run"]) == 0
    records, _ = read_outputs(latest_run(tmp_path))
    r1 = next(r for r in records if r["001"].data == "in00000000001")
    assert r1["245"]["a"] == "Now FOLIO-sourced"
