"""The chq-academic recipe on FOLIO-Exchange and the legacy tool write byte-identical files from the same data.

While the legacy tool is kept as a fallback, a library can switch between the two without collectionHQ
seeing a difference. The legacy tool runs with its example config, which reproduces the layout collectionHQ
gave; FOLIO-Exchange runs a feed on this repository's recipe with no local settings. Recipe minor and patch
versions must not change output bytes, so `^1.0` keeps passing as 1.x versions are added.
"""
import json
import re
from pathlib import Path

import yaml
from folio_chq.cli import main as legacy_main
from folio_exchange.cli import main as fx_main

ROOT = Path(__file__).resolve().parents[1]


def write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def only(folder: Path, pattern: str) -> Path:
    found = sorted(folder.rglob(pattern))
    assert len(found) == 1, f"expected one {pattern} under {folder}, found {[str(f) for f in found]}"
    return found[0]


def test_recipe_and_legacy_tool_write_identical_files(tmp_path, folio, monkeypatch):
    monkeypatch.setenv("FOLIO_PASSWORD", "secret")   # what the mock FOLIO accepts

    cfg = yaml.safe_load((ROOT / "legacy" / "config.example.yaml").read_text(encoding="utf-8"))
    cfg["folio"].update(base_url=folio.url, tenant="diku", username="chq", page_size=2)
    cfg["extract"]["cache_path"] = str(tmp_path / "legacy" / "cache.sqlite")
    cfg["output"]["directory"] = str(tmp_path / "legacy" / "out")
    cfg["delivery"]["method"] = "none"
    assert legacy_main(["-c", str(write_yaml(tmp_path / "legacy" / "config.yaml", cfg)), "run"]) == 0

    site = tmp_path / "fx"
    write_yaml(site / "site.yaml", {
        "folio": {"base_url": folio.url, "tenant": "diku", "username": "chq", "page_size": 2},
        "paths": {"recipes": [str(ROOT / "recipes")]},
        "alerts": {"on": "never"},
    })
    write_yaml(site / "feeds" / "chq.yaml", {"uses": "chq-academic@^1.0", "delivery": {"transport": "none"}})
    assert fx_main(["-s", str(site), "run", "chq"]) == 0
    report = json.loads(only(site / "out" / "chq", "run-report.json").read_text(encoding="utf-8"))
    assert report["recipe"] == "chq-academic" and report["status"] == "success"

    for pattern in ("*.mrc", "*.psv"):
        old, new = only(tmp_path / "legacy" / "out", pattern), only(site / "out" / "chq", pattern)
        assert re.sub(r"\d{8}", "DATE", old.name) == re.sub(r"\d{8}", "DATE", new.name)
        assert new.read_bytes() == old.read_bytes(), f"{new.name} differs from the legacy tool's {old.name}"

    # Not vacuous: bibs from SRS and generated, and item rows with loan counts.
    assert report["build"]["bibs_written"] >= 2 and report["build"]["items_written"] >= 3
    rows = only(site / "out" / "chq", "*.psv").read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("Bib record ID|Item record ID|") and len(rows) == report["build"]["items_written"] + 1
