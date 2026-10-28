# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository. Read `docs/HANDOFF.md` for current status, open questions and next steps.

## What this is

cHQ FOLIO Exchange Recipe (called FOLIOHQ until 28 Oct 2026) is the home of the **collectionHQ Academic recipe for [FOLIO-Exchange](https://github.com/ByYudkowskysTentacle/FOLIO-Exchange)** and the documentation for using it: how a FOLIO library sets up, checks and schedules its feed to collectionHQ Academic. FOLIO-Exchange is the engine (sync, build, checks, delivery); this repository says what collectionHQ's files look like and how to get them there.

- `recipes/chq-academic/<version>.yaml`: the recipe, one file per version, in the layout FOLIO-Exchange's recipe library reads. This is the source; FOLIO-Exchange ships a copy in `src/folio_exchange/recipes/chq-academic/`.
- `docs/setup.md` (the route to go live), `docs/layout.md` (every column and where it comes from), `docs/HANDOFF.md` (status).
- `examples/feeds/chq.yaml` (a commented feed file) and `examples/reference-eureka/` (a site that runs on FOLIO's public Eureka test system).
- `tests/`: the recipe validated by FOLIO-Exchange, the examples run against a mock FOLIO, `docs/layout.md` checked against the recipe, the shipped copy checked against the source, and byte parity with the legacy tool.
- `legacy/`: `folio-chq-extract`, the original one-vendor tool, kept as a fallback until FOLIO-Exchange makes its first real delivery. It has its own `CLAUDE.md`. Fix it only when a bug blocks a library still running it.

**The link collectionHQ uses:** MARC 999 ff $i = the FOLIO instance UUID = the `Bib record ID` column (`instance_id`). 001 = instance HRID. FOLIO-Exchange enforces both on every record.

## Commands

From the repository root:

```bash
pip install -r requirements-dev.txt   # FOLIO-Exchange from GitHub (main), the legacy tool, pytest, ruff
pytest -q                             # recipe tests, offline against the legacy tool's mock FOLIO
ruff check .
folio-exchange recipes validate recipes/chq-academic/1.0.0.yaml
folio-exchange recipes summary chq-academic    # the one-page layout for collectionHQ
```

The legacy tool's tests run from `legacy/`: `pip install -e '.[dev]'`, then `pytest -q`.

## Changing the recipe

- **Versioning:** a minor or patch version must not change a byte of the output. Anything collectionHQ would notice (a column added, removed, renamed or moved, a delimiter, empty value, date format, file name or the link) is a new major version. Add a new `<version>.yaml` with a `changelog` entry; never edit a released version's output.
- **One source:** change the recipe here first, then copy the folder unchanged into FOLIO-Exchange in a pull request there. `tests/test_recipe.py` fails when a file FOLIO-Exchange ships differs from this one.
- **Docs follow the recipe:** update `docs/layout.md` in the same change (a test compares its column table with the newest 1.x), and the recipe's `README.md` version table.
- **Local or shared:** a change one library needs goes in its feed file (`filters`, `options`, `outputs`, `delivery`). Only what collectionHQ wants from every library belongs in the recipe.
- New fields come from FOLIO-Exchange's field registry (`folio-exchange fields`); a field it lacks is a FOLIO-Exchange change first.

## Ground rules

- **Eureka first.** Okapi-based FOLIO keeps working only while the same code serves both; no Okapi-only fixes, features or tests.
- **Never read or export patron data.** Loans are read only for item, dates, renewal count and status.
- **Secrets** come only from environment variables or the OS keyring. Never put them in recipes, feed or site files, logs, commits or chat. Tests never touch the real keyring.
- **Signing in:** do not sign in to a production service (FOLIO tenant, collectionHQ SFTP) with a password yourself. Give the person a command to run, and read only its output.
- **This repo is public.** Never commit credentials, `config.yaml`, `site.yaml` or `feeds/` outside `examples/`, `.env`, cache data or output files, or personal names and emails. Commits use the GitHub noreply address.
- **Recipes stay declarative:** no executable code in recipes.

## FOLIO API facts the recipe and both tools depend on

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
- Loans keep `itemId` and dates after patron anonymization; only `userId` is removed. **Never read or export patron data.** Do not add user or patron endpoints.

## Conventions

- Python 3.10+, type hints, small modules, no heavy dependencies without reason.
- Tests run offline against a mock FOLIO; every bug fix gets a regression test.
- Docs style: use en dashes ( – ) for asides, never em dashes.
