# CLAUDE.md (legacy tool)

`folio-chq-extract`, FOLIOHQ's original tool for collectionHQ Academic, kept here as a fallback until FOLIO-Exchange makes its first real delivery. New work goes into the `chq-academic` recipe (`../recipes/`) or into FOLIO-Exchange, not here. Change this tool only to fix a bug that blocks a library still running it, and keep its output byte-identical to the recipe's (`../tests/test_parity.py` checks it). The repository's ground rules and the FOLIO API facts are in `../CLAUDE.md`.

It writes two files: `chq_bibs_YYYYMMDD.mrc` (MARC 21, UTF-8, ISO 2709; optionally one 949 per item with `output.marc.embed_items`) and `chq_items_YYYYMMDD.psv` (one row per item; `config.example.yaml` matches the cHQ Academic layout), then uploads them over SFTP. `MarcBuilder.finalize` enforces 001 = instance HRID and 999 ff $i = instance UUID = the `Bib record ID` column.

## Commands

Run from this folder:

```bash
pip install -e '.[dev]'
pytest -q                 # all tests run against an in-process mock FOLIO; no network needed
ruff check .              # rules: E, F, I, B, UP (see pyproject.toml)
folio-chq fields          # list every output field
folio-chq -c config.yaml check [--sftp] | run [--full --no-deliver --skip-sync --force] | sync | build | deliver
```

Exit codes: 0 ok, 1 error, 2 blocked by the safety check (files built, not delivered).

## Layout and data flow

```
src/folio_chq/
  cli.py       argparse entry point; `run` = sync -> build -> safety check -> deliver -> prune -> notify
  config.py    YAML + ${ENV} substitution + DEFAULTS deep-merge + validation
  credentials.py  password from config/env, else the OS keyring (optional `keyring` package)
  client.py    FolioClient: login-with-expiry (Okapi and Eureka), retries/backoff, 401 re-login,
               id-keyset paging (`id>"last" sortBy id`), count(), get_all() for reference data
  sync.py      Syncer: reference data (always full), then instances/holdings/items/loans, full or delta;
               fetches SRS MARC for MARC-source instances in batches (POST /source-storage/source-records?idType=INSTANCE)
  cache.py     SQLite cache (zlib-compressed JSON blobs); `gen` column marks rows seen in a full sync
  build.py     one streaming SQL pass: instances LEFT JOIN holdings/items/loanstats ORDER BY instance;
               applies filters, writes MARC and CSV together
  fields.py    ITEM_FIELDS registry + RowBuilder (all computed item fields live here)
  marc.py      SRS JSON -> pymarc; brief MARC for FOLIO-source instances; 949 embedding; ISO 2709 size limits
  dates.py     every timestamp is normalised to a UTC 'YYYY-MM-DDTHH:MM:SS' string, so SQLite MAX()/compare work
  delivery.py  SFTP (paramiko; host key pinned or known_hosts, never auto-accept), two-phase .part upload
               then rename, run pruning, webhook notify
tests/
  mock_folio.py         fake FOLIO HTTP server (login, CQL subset, SRS); extend it whenever you add API calls
  test_end_to_end.py    full CLI runs: outputs, delta and deletions, safety check, retries, custom columns
  test_units.py         dates, config, SFTP, MARC long fields, login retry
deploy/                 cron/systemd/GitHub Actions examples (not run in CI)
```

## Design rules and gotchas

- **Paging:** always use keyset paging (`iter_records`/`iter_pages`) for large collections; offset paging degrades badly. `get_all` (offset paging plus `sortBy id`) is only for small reference tables.
- **Sync safety:** a full sync sets `<entity>.incomplete=1` until it finishes, then deletes rows whose `gen` was not touched. An interrupted run therefore forces another full sync. A delta run that ends with `local count > FOLIO count` means something was deleted, so it falls back to a full resync of that entity.
- **Stale MARC:** the instance upsert clears `marc` when the source is no longer a MARC source. Keep that behaviour.
- **MARC limits:** a record must be ≤ 99,999 bytes and each field ≤ 9,999 bytes (4-digit directory length). `marc.shorten_long_fields` truncates fields at UTF-8 character boundaries. When a record is oversize, 949s are shed but the item rows stay in the CSV. Leader/09 is forced to `a` (UTF-8). The 949 fields go in with `add_ordered_field`.
- **Dates:** normalise on ingest with `dates.norm()`. Legacy note values usually have no time zone, so they are interpreted in `output.items_csv.timezone`; otherwise they shift a day. `dates.parse` has an ISO fast path; dateutil is only the fallback (it was the main performance bottleneck).
- **Delivery integrity:** `deliver` refuses run folders that aren't completed builds. SFTP uploads every file as `.part`, then renames them all. The item-count safety check (`min_item_count_ratio`) compares against the last delivery stored in cache meta.
- **New output field:** add it to `ITEM_FIELDS` and `RowBuilder.build` in `fields.py`, add it to `DATE_FIELDS` if it's a date, then add a fixture and assertion in the mock tests. Config validation picks it up automatically.
- **Performance reference:** the build step processes about 100k bibs and 200k items in ~30 s. Sync time depends on the FOLIO host; 500 records per page is the default.
- **Secrets:** read only from env vars, or from the OS keyring via `credentials.password()` (services `folio-chq-folio` and `folio-chq-sftp`, keyed by username; optional `[keyring]` extra). Tests block the real keyring with an autouse fixture in `conftest.py`, so fake one with `monkeypatch.setitem(sys.modules, 'keyring', ...)`. Env vars: (`FOLIO_PASSWORD`, `SFTP_PASSWORD`, `SFTP_PRIVATE_KEY_PATH`, `SFTP_KEY_PASSPHRASE`, `NOTIFY_WEBHOOK_URL`; `FOLIO_URL`/`FOLIO_TENANT`/`FOLIO_USERNAME` override config). Never commit `config.yaml`, `.env`, `data/` or `out/` (all gitignored).

## Conventions

- Python ≥ 3.10, type hints, small modules, no new heavy dependencies without reason.
- Every bug fix gets a regression test. Keep tests offline: use `MockFolio`, and mock paramiko.
- Update `CHANGELOG.md`, the README field notes, and `config.example.yaml` when behaviour or config changes.
- Org writing style for docs: use en dashes ( – ) for asides, never em dashes.
