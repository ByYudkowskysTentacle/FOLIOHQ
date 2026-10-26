# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository. Read `docs/HANDOFF.md` for current status, open questions and next steps.

## What this is

`folio-chq-extract` (repo: FOLIOHQ) is a Python CLI that pulls bibliographic, item and loan data from the **FOLIO** library services platform through its HTTP APIs, and writes two files for **collectionHQ (cHQ) Academic**:

- `chq_bibs_YYYYMMDD.mrc`: MARC 21 bibs, UTF-8, ISO 2709. Optionally (`output.marc.embed_items`), one 949 field per item.
- `chq_items_YYYYMMDD.psv`: one row per item. The delimiter, extension, null text and columns are configurable; `config.example.yaml` matches the PSV layout cHQ Academic receives.

It then uploads them over SFTP. It runs on a schedule, and routine runs are incremental.

**Bib-to-item link (the cHQ "connector"):** MARC 999 ff $i = the FOLIO instance UUID = the `Bib record ID` column (`instance_id`). cHQ Academic links on this. `MarcBuilder.finalize` enforces it, as it does 001 = instance HRID. With embedding on, the item barcode is also in the bib's 949 $a.

The project is intended to be open source (MIT) and usable by any FOLIO library, so keep library-specific behaviour behind config.

## Commands

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

## FOLIO API facts this code depends on

These were verified against folio-org module descriptors and RAML/OpenAPI in Oct 2026: mod-inventory-storage, mod-source-record-storage, mod-circulation-storage, mod-login, mod-login-keycloak and data-import-raml-storage. To re-check, clone those repos and grep `descriptors/ModuleDescriptor-template.json` and `ramls/`.

| Data | Endpoint | Response key |
|---|---|---|
| Instances | `/instance-storage/instances` | `instances` |
| Holdings | `/holdings-storage/holdings` | `holdingsRecords` |
| Items | `/item-storage/items` | `items` |
| Loans | `/loan-storage/loans` | `loans` |
| MARC | `POST /source-storage/source-records?idType=INSTANCE&recordType=MARC_BIB[&includeShared=true]`, body = list of instance UUIDs | `sourceRecords[].parsedRecord.content` (MARC-in-JSON), `externalIdsHolder.instanceId` |
| Reference data | `/locations` `locations`, `/location-units/{libraries,campuses,institutions}` `loclibs/loccamps/locinsts`, `/material-types` `mtypes`, `/loan-types` `loantypes`, `/call-number-types` `callNumberTypes`, `/item-note-types` `itemNoteTypes`, `/identifier-types` `identifierTypes`, `/classification-types` `classificationTypes` | |
| Auth | `POST /authn/login-with-expiry` returns `folioAccessToken`/`folioRefreshToken` cookies plus `accessTokenExpiration`. The token is also sent as `x-okapi-token`. Falls back to legacy `/authn/login` on 404. | |

- Delta queries use `metadata.updatedDate>="…Z"`. Counts use `totalRecords=exact`, because RMB estimates large counts otherwise.
- Instance `source` values: `MARC`, `CONSORTIUM-MARC` (have SRS); `FOLIO`, `CONSORTIUM-FOLIO`, `LINKED_DATA` (no SRS record, so brief MARC is generated).
- Item fields used: `effectiveLocationId`, `effectiveCallNumberComponents{prefix,callNumber,suffix,typeId}`, `status{name,date}`, `lastCheckIn.dateTime`, `metadata.createdDate`, `notes[]{itemNoteTypeId,note}`, `materialTypeId`, `permanentLoanTypeId`, `discoverySuppress`, `barcode`, `hrid`, `holdingsRecordId`.
- Loans keep `itemId` and dates after patron anonymization; only `userId` is removed. **The tool must never read or export patron data.** Do not add user/patron endpoints.

## Design rules and gotchas

- **Paging:** always use keyset paging (`iter_records`/`iter_pages`) for large collections; offset paging degrades badly. `get_all` (offset paging plus `sortBy id`) is only for small reference tables.
- **Sync safety:** a full sync sets `<entity>.incomplete=1` until it finishes, then deletes rows whose `gen` was not touched. An interrupted run therefore forces another full sync. A delta run that ends with `local count > FOLIO count` means something was deleted, so it falls back to a full resync of that entity.
- **Stale MARC:** the instance upsert clears `marc` when the source is no longer a MARC source. Keep that behaviour.
- **MARC limits:** a record must be ≤ 99,999 bytes and each field ≤ 9,999 bytes (4-digit directory length). `marc.shorten_long_fields` truncates fields at UTF-8 character boundaries. When a record is oversize, 949s are shed but the item rows stay in the CSV. Leader/09 is forced to `a` (UTF-8). The 949 fields go in with `add_ordered_field`.
- **Dates:** normalise on ingest with `dates.norm()`. Legacy note values usually have no time zone, so they are interpreted in `output.items_csv.timezone`; otherwise they shift a day. `dates.parse` has an ISO fast path; dateutil is only the fallback (it was the main performance bottleneck).
- **Delivery integrity:** `deliver` refuses run folders that aren't completed builds. SFTP uploads every file as `.part`, then renames them all. The item-count safety check (`min_item_count_ratio`) compares against the last delivery stored in cache meta.
- **New output field:** add it to `ITEM_FIELDS` and `RowBuilder.build` in `fields.py`, add it to `DATE_FIELDS` if it's a date, then add a fixture and assertion in the mock tests. Config validation picks it up automatically.
- **Performance reference:** the build step processes about 100k bibs and 200k items in ~30 s. Sync time depends on the FOLIO host; 500 records per page is the default.
- **Secrets:** read only from env vars, or for SFTP from the OS keyring (`delivery.stored_password`, service `folio-chq-sftp`, optional `[keyring]` extra) (`FOLIO_PASSWORD`, `SFTP_PASSWORD`, `SFTP_PRIVATE_KEY_PATH`, `SFTP_KEY_PASSPHRASE`, `NOTIFY_WEBHOOK_URL`; `FOLIO_URL`/`FOLIO_TENANT`/`FOLIO_USERNAME` override config). Never commit `config.yaml`, `.env`, `data/` or `out/` (all gitignored).

## Conventions

- Python ≥ 3.10, type hints, small modules, no new heavy dependencies without reason.
- Every bug fix gets a regression test. Keep tests offline: use `MockFolio`, and mock paramiko.
- Update `CHANGELOG.md`, the README field notes, and `config.example.yaml` when behaviour or config changes.
- Org writing style for docs: use en dashes ( – ) for asides, never em dashes.
