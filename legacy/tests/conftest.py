import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))


@pytest.fixture(autouse=True)
def no_real_keyring(monkeypatch):
    """Never touch the developer's real credential store; tests that need one install a fake."""
    monkeypatch.setitem(sys.modules, "keyring", None)
