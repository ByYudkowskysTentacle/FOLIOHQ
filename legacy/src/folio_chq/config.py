"""Configuration loading: YAML file + ``${ENV_VAR}`` substitution + defaults."""
from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_COLUMNS = [
    {"header": "Instance HRID", "field": "instance_hrid"},
    {"header": "Item HRID", "field": "item_hrid"},
    {"header": "Barcode", "field": "barcode"},
    {"header": "Material Type", "field": "material_type"},
    {"header": "Last Circ Date", "field": "last_circ_date"},
    {"header": "Last Checkin Date", "field": "last_checkin_date"},
    {"header": "Status", "field": "status"},
    {"header": "Status Date", "field": "status_date"},
    {"header": "Due Date", "field": "due_date"},
    {"header": "Created Date", "field": "created_date"},
    {"header": "Location Code", "field": "location_code"},
    {"header": "Location", "field": "location_name"},
    {"header": "Library", "field": "library_name"},
    {"header": "Call Number", "field": "call_number"},
    {"header": "Call Number Type", "field": "call_number_type"},
    {"header": "Total Checkouts", "field": "loans_total"},
    {"header": "Checkouts Last 12 Months", "field": "loans_window"},
]

DEFAULTS: dict[str, Any] = {
    "folio": {
        "base_url": "",
        "tenant": "",
        "username": "",
        "password": "${FOLIO_PASSWORD}",
        "page_size": 500,
        "srs_batch_size": 200,
        "timeout_seconds": 120,
        "max_retries": 5,
        "verify_tls": True,
        "srs_include_shared": False,
    },
    "extract": {
        "mode": "auto",
        "full_refresh_days": 30,
        "cache_path": "./data/cache.sqlite",
        "include_suppressed_instances": False,
        "include_suppressed_items": False,
        "exclude_item_statuses": [],
        "include_location_codes": [],
        "exclude_location_codes": [],
        "include_items_without_barcode": True,
        "loan_window_months": 12,
        "last_circ_date_from": "checkout",
        "bibs_without_items": False,
    },
    "legacy": {
        "created_date_note_type": None,
        "circ_count_note_type": None,
        "last_circ_date_note_type": None,
    },
    "output": {
        "directory": "./out",
        "file_prefix": "chq",
        "date_stamp_format": "%Y%m%d",
        "min_item_count_ratio": 0.9,
        "marc": {
            "split_every": 0,
            "embed_items": True,
            "item_field_tag": "949",
            "item_subfields": {
                "a": "barcode",
                "b": "item_hrid",
                "c": "call_number",
                "l": "location_code",
                "t": "material_type",
                "s": "status",
            },
            "strip_existing_item_field": True,
            "max_items_per_record": 500,
        },
        "items_csv": {
            "delimiter": ",",
            "file_extension": "csv",
            "null_value": "",
            "date_format": "%Y-%m-%d",
            "timezone": "UTC",
            "columns": DEFAULT_COLUMNS,
        },
    },
    "delivery": {
        "method": "local",
        "keep_local_runs": 5,
        "sftp": {
            "host": "",
            "port": 22,
            "username": "",
            "password": "${SFTP_PASSWORD}",
            "private_key_path": "${SFTP_PRIVATE_KEY_PATH}",
            "private_key_passphrase": "${SFTP_KEY_PASSPHRASE}",
            "remote_dir": ".",
            "upload_mode": "staged",
            "known_hosts_path": "~/.ssh/known_hosts",
            "host_key_fingerprint": "",
        },
    },
    "notify": {
        "webhook_url": "${NOTIFY_WEBHOOK_URL}",
        "on": "failure",
    },
}

_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _subst(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), value)
    if isinstance(value, dict):
        return {k: _subst(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_subst(v) for v in value]
    return value


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | os.PathLike | None) -> dict:
    data: dict = {}
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg = _subst(_merge(DEFAULTS, data))
    # Environment overrides for the connection, so containers need no config edits.
    for key, env in (("base_url", "FOLIO_URL"), ("tenant", "FOLIO_TENANT"), ("username", "FOLIO_USERNAME")):
        if os.environ.get(env):
            cfg["folio"][key] = os.environ[env]
    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    mode = cfg["extract"]["mode"]
    if mode not in {"auto", "full", "delta"}:
        raise ValueError(f"extract.mode must be auto, full or delta (got {mode!r})")
    if cfg["extract"]["last_circ_date_from"] not in {"checkout", "any"}:
        raise ValueError("extract.last_circ_date_from must be 'checkout' or 'any'")
    if cfg["delivery"]["method"] not in {"sftp", "local", "none"}:
        raise ValueError("delivery.method must be sftp, local or none")
    if cfg["delivery"]["sftp"]["upload_mode"] not in {"staged", "direct"}:
        raise ValueError("delivery.sftp.upload_mode must be staged or direct")
    tag = str(cfg["output"]["marc"]["item_field_tag"])
    if not (len(tag) == 3 and tag.isdigit() and int(tag) >= 10):
        raise ValueError("output.marc.item_field_tag must be a 3-digit data field tag (010-999)")
    ext = str(cfg["output"]["items_csv"]["file_extension"])
    if not ext.isalnum() or ext.lower() == "mrc":
        raise ValueError(f"output.items_csv.file_extension must be letters/digits only and not 'mrc' (got {ext!r})")
    from .fields import ITEM_FIELDS

    for col in cfg["output"]["items_csv"]["columns"]:
        if col.get("field") not in ITEM_FIELDS:
            raise ValueError(f"Unknown items_csv column field {col.get('field')!r}. Valid: {', '.join(sorted(ITEM_FIELDS))}")
    for code, field in cfg["output"]["marc"]["item_subfields"].items():
        if field not in ITEM_FIELDS:
            raise ValueError(f"Unknown MARC item subfield source {field!r} for ${code}")
