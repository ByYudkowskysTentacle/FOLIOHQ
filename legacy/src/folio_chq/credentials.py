"""Passwords from config/environment, else from the OS keyring (Windows Credential
Manager, macOS Keychain, Secret Service). The keyring is optional:
pip install 'folio-chq-extract[keyring]'."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

FOLIO_SERVICE = "folio-chq-folio"
SFTP_SERVICE = "folio-chq-sftp"


def password(configured: str | None, service: str, username: str | None) -> str | None:
    """The configured password if set, else the one stored under (service, username)."""
    if configured:
        return configured
    if not username:
        return None
    try:
        import keyring
    except ImportError:
        return None
    try:
        return keyring.get_password(service, username)
    except Exception as exc:  # noqa: BLE001 - any backend failure just means "nothing stored"
        log.warning("Could not read the %s password from the system keyring: %s", service, exc)
        return None


def source(configured: str | None, service: str, username: str | None) -> str:
    """Where password() finds the secret, for check output. Never includes the secret."""
    if configured:
        return "config/environment"
    if password(None, service, username):
        return f"system keyring ({service})"
    return "NOT FOUND"
