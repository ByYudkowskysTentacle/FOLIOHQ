from unittest import mock

import pytest

from folio_chq import delivery
from folio_chq.config import load_config
from folio_chq.dates import fmt, norm
from folio_chq.marc import _set_instance_link


def test_norm_dates():
    assert norm("2024-03-01T23:30:00.000-05:00") == "2024-03-02T04:30:00"
    assert norm("2024-03-01") == "2024-03-01T00:00:00"
    assert norm("not a date") is None
    from zoneinfo import ZoneInfo
    assert fmt("2024-03-02T04:30:00Z", "%Y-%m-%d", ZoneInfo("America/New_York")) == "2024-03-01"


def test_config_rejects_unknown_column(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("output:\n  items_csv:\n    columns:\n      - {header: X, field: nope}\n")
    with pytest.raises(ValueError, match="Unknown items_csv column"):
        load_config(p)


def test_config_env_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_PASSWORD", "s3cret")
    monkeypatch.setenv("FOLIO_URL", "https://folio.example.edu")
    p = tmp_path / "c.yaml"
    p.write_text("folio:\n  tenant: t\n")
    cfg = load_config(p)
    assert cfg["folio"]["password"] == "s3cret"
    assert cfg["folio"]["base_url"] == "https://folio.example.edu"


def test_sftp_uploads_atomically(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a")
    with mock.patch("paramiko.SSHClient") as ssh:
        sftp = ssh.return_value.open_sftp.return_value
        out = delivery.deliver_sftp([f], {"host": "h", "username": "u", "remote_dir": "/in", "host_key_fingerprint": "SHA256:abc"})
    sftp.put.assert_called_once_with(str(f), "/in/x.csv.part", confirm=True)
    sftp.posix_rename.assert_called_once_with("/in/x.csv.part", "/in/x.csv")
    assert out == ["/in/x.csv"]


def test_fingerprint_format():
    key = mock.Mock()
    key.asbytes.return_value = b"key-bytes"
    assert delivery.sha256_fingerprint(key).startswith("SHA256:")


def test_long_field_is_truncated_and_readable():
    from io import BytesIO

    from pymarc import Field, Indicators, MARCReader, Record, Subfield

    from folio_chq.config import DEFAULTS
    from folio_chq.marc import MarcBuilder

    rec = Record(leader="00000nam a2200000 a 4500")
    rec.add_field(Field(tag="001", data="x"))
    rec.add_field(Field(tag="245", indicators=Indicators("0", "0"), subfields=[Subfield("a", "T")]))
    rec.add_field(Field(tag="505", indicators=Indicators("0", " "), subfields=[Subfield("a", "é" * 8000)]))
    mb = MarcBuilder(DEFAULTS, lambda n, v: v)
    data = mb.finalize(rec, {"hrid": "in1"}, [{"barcode": "B1"}])
    assert mb.long_fields == 1
    out = next(MARCReader(BytesIO(data), to_unicode=True, force_utf8=True))
    assert out is not None and out["001"].data == "in1" and out["949"]["a"] == "B1"
    assert len(out["505"]["a"].encode()) < 9999


def test_legacy_dates_keep_their_day_in_local_timezone():
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Chicago")
    assert fmt(norm("3/15/1998", tz), "%Y-%m-%d", tz) == "1998-03-15"
    assert fmt(norm("1998-03-15", tz), "%Y-%m-%d", tz) == "1998-03-15"


def test_sftp_renames_only_after_all_uploads(tmp_path):
    a, b = tmp_path / "a.mrc", tmp_path / "b.csv"
    a.write_text("a")
    b.write_text("b")
    with mock.patch("paramiko.SSHClient") as ssh:
        sftp = ssh.return_value.open_sftp.return_value
        sftp.put.side_effect = [None, OSError("connection lost")]
        with pytest.raises(OSError):
            delivery.deliver_sftp([a, b], {"host": "h", "username": "u", "host_key_fingerprint": "SHA256:x"})
    sftp.posix_rename.assert_not_called()


def test_login_retries_transient_errors(monkeypatch):
    from folio_chq import client as cm

    monkeypatch.setattr(cm.time, "sleep", lambda s: None)
    c = cm.FolioClient("http://folio", "t", "u", "p")
    calls = {"n": 0}

    def fake_login():
        calls["n"] += 1
        if calls["n"] == 1:
            raise cm._TransientLoginError("502")
        c._token = "tok"

    monkeypatch.setattr(c, "login", fake_login)
    resp = mock.Mock(status_code=200, ok=True, content=b"{}", json=lambda: {"ok": 1})
    monkeypatch.setattr(c.session, "request", lambda *a, **k: resp)
    assert c.get("/x") == {"ok": 1}
    assert calls["n"] == 2


def test_instance_link_is_set_and_keeps_other_999_subfields():
    from pymarc import Field, Indicators, Record, Subfield

    rec = Record()
    rec.add_field(Field(tag="999", indicators=Indicators("f", "f"), subfields=[Subfield("i", "wrong"), Subfield("s", "srs-id")]))
    assert _set_instance_link(rec, "inst-uuid") is False
    assert [(s.code, s.value) for s in rec["999"].subfields] == [("i", "inst-uuid"), ("s", "srs-id")]
    assert _set_instance_link(rec, "inst-uuid") is True

    bare = Record()
    bare.add_field(Field(tag="999", indicators=Indicators(" ", " "), subfields=[Subfield("a", "local")]))
    assert _set_instance_link(bare, "inst-uuid") is False
    links = [f for f in bare.get_fields("999") if f.indicator1 == "f"]
    assert len(links) == 1 and links[0]["i"] == "inst-uuid"
    assert len(bare.get_fields("999")) == 2                      # the local 999 is untouched


def test_config_rejects_bad_file_extension(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("output:\n  items_csv:\n    file_extension: mrc\n")
    with pytest.raises(ValueError, match="file_extension"):
        load_config(p)


def test_sftp_check_lists_without_writing(tmp_path):
    with mock.patch("paramiko.SSHClient") as ssh:
        sftp = ssh.return_value.open_sftp.return_value
        sftp.listdir.return_value = ["b.psv", "a.mrc"]
        names = delivery.check_sftp({"host": "h", "username": "u", "remote_dir": "/in/", "host_key_fingerprint": "SHA256:x"})
    assert names == ["a.mrc", "b.psv"]
    sftp.listdir.assert_called_once_with("/in")
    assert not sftp.put.called and not sftp.remove.called and not sftp.rename.called
    ssh.return_value.close.assert_called_once()


def test_check_sftp_command_reports_failure(tmp_path, capsys):
    from folio_chq.cli import main

    p = tmp_path / "c.yaml"
    p.write_text(f"output:\n  directory: {tmp_path.as_posix()}/out\ndelivery:\n  sftp:\n    host: h\n    username: u\n")
    with mock.patch("folio_chq.cli.check_sftp", side_effect=OSError("refused")):
        assert main(["-c", str(p), "check", "--sftp"]) == 1
    assert "FAILED   OSError: refused" in capsys.readouterr().out


def test_sftp_direct_mode_uploads_to_final_names_without_stat_or_rename(tmp_path):
    a, b = tmp_path / "a.mrc", tmp_path / "b.psv"
    a.write_text("a")
    b.write_text("b")
    with mock.patch("paramiko.SSHClient") as ssh:
        sftp = ssh.return_value.open_sftp.return_value
        out = delivery.deliver_sftp([a, b], {"host": "h", "username": "u", "remote_dir": "in",
                                             "upload_mode": "direct", "host_key_fingerprint": "SHA256:x"})
    assert out == ["in/a.mrc", "in/b.psv"]
    assert sftp.put.call_args_list == [mock.call(str(a), "in/a.mrc", confirm=False),
                                       mock.call(str(b), "in/b.psv", confirm=False)]
    assert not sftp.rename.called and not sftp.posix_rename.called and not sftp.remove.called


def test_sftp_check_tolerates_upload_only_account():
    with mock.patch("paramiko.SSHClient") as ssh:
        ssh.return_value.open_sftp.return_value.listdir.side_effect = PermissionError(13, "Permission denied")
        assert delivery.check_sftp({"host": "h", "username": "u", "host_key_fingerprint": "SHA256:x"}) is None


def test_password_falls_back_to_keyring(monkeypatch):
    import sys
    import types

    fake = types.SimpleNamespace(get_password=lambda service, user: f"{service}/{user}")
    monkeypatch.setitem(sys.modules, "keyring", fake)
    assert delivery.stored_password({"username": "u", "password": ""}) == "folio-chq-sftp/u"
    assert delivery.stored_password({"username": "u", "password": "from-env"}) == "from-env"
    with mock.patch("paramiko.SSHClient") as ssh:
        delivery.check_sftp({"host": "h", "username": "u", "password": "", "host_key_fingerprint": "SHA256:x"})
    assert ssh.return_value.connect.call_args.kwargs["password"] == "folio-chq-sftp/u"


def test_config_rejects_bad_upload_mode(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("delivery:" + chr(10) + "  sftp:" + chr(10) + "    upload_mode: fast" + chr(10))
    with pytest.raises(ValueError, match="upload_mode"):
        load_config(p)
