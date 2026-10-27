import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "legacy" / "tests"))   # the mock FOLIO both tools are tested against


@pytest.fixture(autouse=True)
def no_real_keyring(monkeypatch):
    """Never touch the developer's real credential store."""
    monkeypatch.setitem(sys.modules, "keyring", None)


@pytest.fixture(autouse=True)
def no_real_secrets_in_env(monkeypatch):
    """Tests decide which secrets and overrides exist; a developer's own environment must not leak in."""
    for name in ("FOLIO_PASSWORD", "FOLIO_URL", "FOLIO_TENANT", "FOLIO_USERNAME", "SFTP_PASSWORD",
                 "SFTP_PRIVATE_KEY_PATH", "SFTP_KEY_PASSPHRASE", "NOTIFY_WEBHOOK_URL", "FOLIO_EXCHANGE_SITE"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def folio():
    """A running mock FOLIO with the legacy tool's fixture data; loan dates marked RECENT are made relative to now."""
    from mock_folio import MockFolio, default_data

    def recent(days):
        return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = default_data()
    for loan in data["loans"]:
        if loan.get("loanDate") == "RECENT":
            loan["loanDate"] = recent(30)
        if loan.get("returnDate") == "RECENT_RETURN":
            loan["returnDate"] = recent(10)
    with MockFolio(data) as m:
        yield m
