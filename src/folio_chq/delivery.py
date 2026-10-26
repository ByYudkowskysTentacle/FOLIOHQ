"""Deliver output files to collectionHQ (SFTP) and send notifications."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import shutil
from pathlib import Path

import requests

log = logging.getLogger(__name__)


def sha256_fingerprint(key) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


KEYRING_SERVICE = "folio-chq-sftp"


def stored_password(sftp_cfg: dict) -> str | None:
    """The configured password, else one saved in the OS keyring (Windows Credential
    Manager, macOS Keychain, Secret Service) under KEYRING_SERVICE and the username."""
    if sftp_cfg.get("password"):
        return sftp_cfg["password"]
    try:
        import keyring
    except ImportError:  # optional extra: pip install 'folio-chq-extract[keyring]'
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, sftp_cfg["username"])
    except Exception as exc:  # noqa: BLE001 - any backend failure just means "nothing stored"
        log.warning("Could not read the SFTP password from the system keyring: %s", exc)
        return None


def _connect(sftp_cfg: dict):
    import paramiko

    host = sftp_cfg["host"]
    if not host:
        raise ValueError("delivery.sftp.host is not set")
    client = paramiko.SSHClient()
    expected = (sftp_cfg.get("host_key_fingerprint") or "").strip()
    if expected:

        class _Pinned(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, _client, hostname, key):
                got = sha256_fingerprint(key)
                if got != expected:
                    raise paramiko.SSHException(f"Host key for {hostname} is {got}, expected {expected}")

        client.set_missing_host_key_policy(_Pinned())
    else:
        kh = os.path.expanduser(sftp_cfg.get("known_hosts_path") or "~/.ssh/known_hosts")
        if os.path.exists(kh):
            client.load_host_keys(kh)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

    key_path = (sftp_cfg.get("private_key_path") or "").strip()
    client.connect(
        hostname=host,
        port=int(sftp_cfg.get("port") or 22),
        username=sftp_cfg["username"],
        password=None if key_path else stored_password(sftp_cfg),
        key_filename=os.path.expanduser(key_path) if key_path else None,
        passphrase=sftp_cfg.get("private_key_passphrase") or None,
        look_for_keys=False,
        allow_agent=False,
        timeout=60,
    )
    return client


def _remote_dir(sftp_cfg: dict) -> str:
    return (sftp_cfg.get("remote_dir") or ".").rstrip("/") or "."


def check_sftp(sftp_cfg: dict) -> list[str] | None:
    """Log in, verify the host key and list the remote folder. Writes nothing.

    Returns None when login works but listing is refused, as on upload-only accounts."""
    client = _connect(sftp_cfg)
    try:
        sftp = client.open_sftp()
        try:
            names: list[str] | None = sorted(sftp.listdir(_remote_dir(sftp_cfg)))
        except PermissionError:
            names = None
        sftp.close()
    finally:
        client.close()
    return names


def deliver_sftp(files: list[Path], sftp_cfg: dict) -> list[str]:
    host = sftp_cfg["host"]
    client = _connect(sftp_cfg)
    uploaded = []
    try:
        sftp = client.open_sftp()
        remote_dir = _remote_dir(sftp_cfg)
        if (sftp_cfg.get("upload_mode") or "staged") == "direct":
            # Upload-only accounts can't stat or rename. On object-store-backed
            # servers (e.g. AWS Transfer Family) a file only appears once complete.
            for f in files:
                final = f"{remote_dir}/{f.name}"
                log.info("Uploading %s (%s bytes) to %s:%s", f.name, f.stat().st_size, host, final)
                sftp.put(str(f), final, confirm=False)
                uploaded.append(final)
            sftp.close()
            return uploaded
        # Phase 1: upload everything as .part, so a dropped connection never
        # leaves new bibs next to an old items file (or vice versa).
        staged = []
        for f in files:
            final = f"{remote_dir}/{f.name}"
            tmp = final + ".part"
            log.info("Uploading %s (%s bytes) to %s:%s", f.name, f.stat().st_size, host, tmp)
            sftp.put(str(f), tmp, confirm=True)
            staged.append((tmp, final))
        # Phase 2: all uploads succeeded; rename them into place.
        for tmp, final in staged:
            try:
                sftp.posix_rename(tmp, final)
            except OSError:  # server without posix-rename extension
                try:
                    sftp.remove(final)
                except OSError:
                    pass
                sftp.rename(tmp, final)
            uploaded.append(final)
        sftp.close()
    finally:
        client.close()
    return uploaded


def prune_runs(out_dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    runs = sorted((p for p in out_dir.iterdir() if p.is_dir() and p.name[:1].isdigit()), key=lambda p: p.name)
    for old in runs[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
        log.info("Removed old run %s", old.name)


def notify(url: str, text: str) -> None:
    if not url:
        return
    try:
        requests.post(url, json={"text": text}, timeout=30)
    except requests.RequestException as exc:
        log.warning("Notification failed: %s", exc)
