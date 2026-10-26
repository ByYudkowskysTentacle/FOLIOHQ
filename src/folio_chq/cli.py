"""Command-line interface: folio-chq {check,sync,build,deliver,run,fields}."""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
import traceback
from pathlib import Path

from . import __version__
from .build import build
from .cache import Cache
from .client import FolioClient, FolioError
from .config import load_config
from .dates import now_utc
from .delivery import deliver_sftp, notify, prune_runs
from .fields import ITEM_FIELDS
from .sync import ENTITIES, REFDATA, Syncer

log = logging.getLogger("folio_chq")


class SafetyCheckFailed(RuntimeError):
    pass


def _setup_logging(out_dir: Path, verbose: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for old in [h for h in root.handlers if getattr(h, "_folio_chq", False)]:
        root.removeHandler(old)
        old.close()
    for h in (logging.StreamHandler(sys.stderr), logging.FileHandler(out_dir / "folio-chq.log", encoding="utf-8")):
        h.setFormatter(fmt)
        h._folio_chq = True
        root.addHandler(h)
    for noisy in ("urllib3", "paramiko"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _client(cfg: dict) -> FolioClient:
    f = cfg["folio"]
    return FolioClient(
        f["base_url"], f["tenant"], f["username"], f["password"],
        timeout=float(f["timeout_seconds"]), max_retries=int(f["max_retries"]),
        verify_tls=bool(f["verify_tls"]), user_agent=f"folio-chq-extract/{__version__}",
    )


def _report(obj) -> dict:
    if dataclasses.is_dataclass(obj):
        out = {}
        for f in dataclasses.fields(obj):
            v = getattr(obj, f.name)
            out[f.name] = dict(v) if isinstance(v, dict) else v
        return out
    return obj


# ------------------------------------------------------------------ commands
def cmd_check(cfg: dict, _args) -> int:
    client = _client(cfg)
    client.login()
    print(f"Logged in to {client.base_url} (tenant {client.tenant}) as {client.username}")
    ok = True
    checks = [(f"{k} ({p})", p) for k, (p, _key) in ENTITIES.items()]
    checks += [(f"{k} ({p})", p) for k, (p, _key) in REFDATA.items()]
    checks.append(("MARC source records (/source-storage/source-records)", "/source-storage/source-records"))
    for label, path in checks:
        try:
            if path.startswith("/source-storage"):
                client.get(path, {"limit": 0})
                print(f"  OK       {label}")
            else:
                print(f"  OK       {label}: {client.count(path):,} records")
        except FolioError as exc:
            ok = False
            print(f"  FAILED   {label}: {str(exc)[:160]}")
    if not ok:
        print("\nSome endpoints failed. Check the service account's permissions (see README).")
    return 0 if ok else 1


def cmd_fields(_cfg, _args) -> int:
    width = max(map(len, ITEM_FIELDS))
    for name, desc in ITEM_FIELDS.items():
        print(f"{name:<{width}}  {desc}")
    return 0


def do_sync(cfg: dict, full: bool) -> dict:
    cache = Cache(cfg["extract"]["cache_path"])
    try:
        rep = Syncer(_client(cfg), cache, cfg).run(force_full=full)
    finally:
        cache.close()
    return _report(rep)


def do_build(cfg: dict, run_dir: Path) -> dict:
    cache = Cache(cfg["extract"]["cache_path"])
    try:
        rep = build(cache, cfg, run_dir)
    finally:
        cache.close()
    return _report(rep)


def safety_check(cfg: dict, items_written: int) -> None:
    ratio = float(cfg["output"]["min_item_count_ratio"] or 0)
    cache = Cache(cfg["extract"]["cache_path"])
    try:
        prev = cache.get_meta("last_delivered_items")
    finally:
        cache.close()
    if prev and ratio and items_written < int(prev) * ratio:
        raise SafetyCheckFailed(
            f"Item count fell from {int(prev):,} to {items_written:,} "
            f"(below {ratio:.0%} of the last delivery). Files were built but not delivered. "
            "Re-run with --force if this drop is expected."
        )


def do_deliver(cfg: dict, run_dir: Path, items_written: int | None) -> list[str]:
    item_ext = "." + str(cfg["output"]["items_csv"]["file_extension"])
    files = sorted(p for p in run_dir.iterdir() if p.suffix in {".mrc", item_ext})
    method = cfg["delivery"]["method"]
    sent: list[str] = []
    if method == "sftp":
        sent = deliver_sftp(files, cfg["delivery"]["sftp"])
    else:
        log.info("Delivery method is %r; files left in %s", method, run_dir)
    if items_written is not None:
        cache = Cache(cfg["extract"]["cache_path"])
        try:
            cache.set_meta("last_delivered_items", str(items_written))
            cache.set_meta("last_delivered_at", now_utc().isoformat())
        finally:
            cache.close()
    return sent


def _latest_run(out_dir: Path) -> Path:
    runs = sorted(p for p in out_dir.iterdir() if p.is_dir() and p.name[:1].isdigit())
    if not runs:
        raise FileNotFoundError(f"No runs found in {out_dir}")
    return runs[-1]


def cmd_run(cfg: dict, args) -> int:
    out_dir = Path(cfg["output"]["directory"])
    run_dir = out_dir / now_utc().strftime("%Y%m%d-%H%M%S")
    report: dict = {"version": __version__, "started": now_utc().isoformat(), "run_dir": str(run_dir)}
    status, code = "success", 0
    try:
        if not args.skip_sync:
            report["sync"] = do_sync(cfg, args.full)
        report["build"] = do_build(cfg, run_dir)
        items = report["build"]["items_written"]
        if args.no_deliver:
            log.info("--no-deliver: files left in %s", run_dir)
        else:
            if not args.force:
                safety_check(cfg, items)
            report["delivered"] = do_deliver(cfg, run_dir, items)
        prune_runs(out_dir, int(cfg["delivery"]["keep_local_runs"]))
    except SafetyCheckFailed as exc:
        status, code = "blocked", 2
        report["error"] = str(exc)
        log.error("%s", exc)
    except Exception as exc:  # noqa: BLE001 - top-level: report every failure
        status, code = "failed", 1
        report["error"] = f"{type(exc).__name__}: {exc}"
        log.error("Run failed: %s", exc)
        log.debug("%s", traceback.format_exc())
    report["status"] = status
    report["finished"] = now_utc().isoformat()
    if run_dir.exists():
        (run_dir / "run-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _notify(cfg, report)
    print(json.dumps({k: report.get(k) for k in ("status", "run_dir", "error") if report.get(k)}, indent=2))
    return code


def _notify(cfg: dict, report: dict) -> None:
    n = cfg["notify"]
    if not n.get("webhook_url"):
        return
    if n.get("on") != "always" and report["status"] == "success":
        return
    b = report.get("build") or {}
    text = (
        f"folio-chq-extract [{cfg['folio']['tenant']}]: {report['status'].upper()}. "
        f"Bibs {b.get('bibs_written', '?'):,}, items {b.get('items_written', '?'):,}."
        if b else f"folio-chq-extract [{cfg['folio']['tenant']}]: {report['status'].upper()}."
    )
    if report.get("error"):
        text += f" {report['error']}"
    notify(n["webhook_url"], text)


def cmd_sync(cfg, args) -> int:
    print(json.dumps(do_sync(cfg, args.full), indent=2, default=str))
    return 0


def cmd_build(cfg, _args) -> int:
    run_dir = Path(cfg["output"]["directory"]) / now_utc().strftime("%Y%m%d-%H%M%S")
    rep = do_build(cfg, run_dir)
    (run_dir / "run-report.json").write_text(json.dumps({"build": rep}, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), **rep}, indent=2, default=str))
    return 0


def cmd_deliver(cfg, args) -> int:
    run_dir = Path(args.run_dir) if args.run_dir else _latest_run(Path(cfg["output"]["directory"]))
    rep_path = run_dir / "run-report.json"
    report = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    items = (report.get("build") or {}).get("items_written")
    complete = items is not None and report.get("status", "success") in {"success", "blocked"}
    if not complete and not args.force:
        raise SafetyCheckFailed(
            f"{run_dir} is not a completed build (status {report.get('status', 'unknown')!r}); "
            "refusing to deliver possibly partial files. Use --force to override."
        )
    if items is not None and not args.force:
        safety_check(cfg, items)
    sent = do_deliver(cfg, run_dir, items)
    print(json.dumps({"run_dir": str(run_dir), "delivered": sent}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="folio-chq", description="Extract FOLIO data for collectionHQ Academic.")
    p.add_argument("-c", "--config", default="config.yaml", help="path to config file (default: config.yaml)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="test login, permissions and record counts")
    sub.add_parser("fields", help="list fields available for CSV columns and MARC item subfields")
    s = sub.add_parser("sync", help="update the local cache from FOLIO")
    s.add_argument("--full", action="store_true", help="ignore the cache and fetch everything")
    sub.add_parser("build", help="write output files from the local cache")
    d = sub.add_parser("deliver", help="send a built run to collectionHQ")
    d.add_argument("run_dir", nargs="?", help="run directory (default: latest)")
    d.add_argument("--force", action="store_true", help="skip the item-count safety check")
    r = sub.add_parser("run", help="sync, build and deliver (use this for scheduled runs)")
    r.add_argument("--full", action="store_true", help="force a full refresh from FOLIO")
    r.add_argument("--no-deliver", action="store_true", help="build files but do not send them")
    r.add_argument("--skip-sync", action="store_true", help="rebuild from the cache without contacting FOLIO")
    r.add_argument("--force", action="store_true", help="skip the item-count safety check")
    args = p.parse_args(argv)

    if args.command == "fields":
        return cmd_fields(None, args)
    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    _setup_logging(Path(cfg["output"]["directory"]), args.verbose)
    handler = {"check": cmd_check, "sync": cmd_sync, "build": cmd_build, "deliver": cmd_deliver, "run": cmd_run}
    try:
        return handler[args.command](cfg, args)
    except SafetyCheckFailed as exc:
        log.error("%s", exc)
        return 2
    except (FolioError, OSError, ValueError) as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
