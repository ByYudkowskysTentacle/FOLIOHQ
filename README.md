# folio-chq-extract

Extracts bibliographic and item/circulation data from the [FOLIO](https://www.folio.org/) library services platform for **collectionHQ Academic**, and keeps it up to date on a schedule.

Each run produces two files and sends them to collectionHQ over SFTP:

| File | Contents |
|---|---|
| `chq_bibs_YYYYMMDD.mrc` | Full MARC 21 bibliographic records (UTF-8, ISO 2709) from FOLIO Source Record Storage. Optionally, each record also carries one **949** field per item (barcode, item HRID, call number, location, material type, status). |
| `chq_items_YYYYMMDD.psv` | One row per item, pipe-delimited: bib record ID, barcode, material type, last circ date, status, created date, location, call number, loan and renewal counts, and more. The columns, delimiter and extension are configurable; the example config matches the layout collectionHQ Academic receives. |

**How bibs and items link:** every bib carries the FOLIO instance UUID in **999 ff $i**, and the item file's `Bib record ID` column holds the same UUID. collectionHQ Academic links on that. MARC **001** holds the instance HRID, available as the `instance_hrid` column, and with embedded 949 fields the item **barcode** links them as well.

> This is a community project. It is not affiliated with or endorsed by collectionHQ or the FOLIO project. Confirm the file layout with your collectionHQ implementation contact before you go live.

## Features

- Works with Okapi-based FOLIO and Eureka (Kong gateway) deployments, and supports ECS consortium member tenants.
- **Incremental updates.** A local SQLite cache means a routine run fetches only the records that changed since the last run. Deleted records are detected and trigger a full resync, and a full refresh also runs on a schedule (every 30 days by default).
- **FOLIO-source instances** (records with no MARC in SRS) get a brief MARC record generated from the instance data, so no titles are lost.
- **Legacy data from a migration.** FOLIO stamps migrated items with the migration date as their created date, and keeps no lifetime circulation count. If your migration stored those values in item notes, the tool can use them.
- **Safety check.** If the item count drops sharply compared with the last delivery, the run is blocked, so collectionHQ never receives a half-empty extract.
- Configurable columns, headers, delimiter, date format, MARC item tag, and location/status filters, so other libraries can match their own collectionHQ specification.
- Retries with backoff, automatic re-login, atomic SFTP uploads (`.part` then rename), a JSON run report, and optional Slack or Teams alerts.

## Quick start

```bash
pip install git+https://github.com/ByYudkowskysTentacle/FOLIOHQ.git   # or: pip install -e . from a clone
cp config.example.yaml config.yaml                                   # then edit it
export FOLIO_PASSWORD='...'  SFTP_PASSWORD='...'   # or keep both passwords in the OS keyring (below)

folio-chq check                 # test login, permissions and record counts
folio-chq run --no-deliver      # first run: build the files and inspect them in ./out/
folio-chq run                   # sync, build and upload to collectionHQ
```

The first run is always a full extract. On a large collection (1M+ items) it can take an hour or more, depending on your FOLIO hosting. Later runs are incremental.

### Commands

| Command | What it does |
|---|---|
| `folio-chq check` | Logs in and checks that every endpoint the tool needs is readable |
| `folio-chq check --sftp` | Logs in to the SFTP server, verifies its host key and lists the remote folder. Uploads nothing |
| `folio-chq run` | Sync, build, safety check, deliver. **Use this for scheduled runs.** Options: `--full`, `--no-deliver`, `--skip-sync`, `--force` |
| `folio-chq sync [--full]` | Update the local cache only |
| `folio-chq build` | Write output files from the cache, without contacting FOLIO |
| `folio-chq deliver [RUN_DIR]` | Upload a built run (the latest by default) |
| `folio-chq fields` | List every field available for CSV columns and MARC item subfields |

Exit codes: `0` success, `1` failure, `2` blocked by the safety check (files were built but not sent).

## FOLIO service account

Create a dedicated user, for example `chq_extract`, with **read-only** access. It needs these permissions (or a permission set that includes them):

```
inventory-storage.instances.collection.get
inventory-storage.holdings.collection.get
inventory-storage.items.collection.get
inventory-storage.locations.collection.get
inventory-storage.location-units.libraries.collection.get
inventory-storage.location-units.campuses.collection.get
inventory-storage.location-units.institutions.collection.get
inventory-storage.material-types.collection.get
inventory-storage.loan-types.collection.get
inventory-storage.call-number-types.collection.get
inventory-storage.item-note-types.collection.get
inventory-storage.identifier-types.collection.get
inventory-storage.classification-types.collection.get
source-storage.source-records.collection.get
circulation-storage.loans.collection.get
```

No patron data is read or exported: loans are used only for item ID, dates, renewal count and status.

## Field notes

- **Last Circ Date** is the most recent checkout recorded in FOLIO, or the legacy value if that is newer. Set `extract.last_circ_date_from: any` to use the latest checkout, return or check-in scan instead. **Loan Return Date** (`last_return_date`) is the most recent return.
- **Number of loans** (`loans_total`) counts FOLIO loans plus the legacy count, if one is configured. Loans keep their item and dates after patron anonymization, so anonymizing does not reduce the counts.
- **Created Date** is the item record's creation date, or the legacy note value if one is configured. Without a legacy note, migrated items show the migration date.
- **Call Number** is FOLIO's *effective* call number: the item-level call number if one exists, otherwise the holdings call number, with prefix and suffix. The example config uses it for cHQ's `Item_level_call_number` column, so items whose call number lives on the holdings record are not left blank. `item_level_call_number` is the item record's own value only, and `call_number_full` adds volume, enumeration, chronology and copy.
- **Location** is the item's *effective* location, as FOLIO computes it: the item's temporary location if one is set, otherwise its permanent location, otherwise the holdings location. `location_name_code` gives "Name [code]", the form in cHQ's sample. `location_name`, `location_code` and `permanent_location_code` are also available.
- **Bound-with items** are reported under the instance their holdings belong to.
- **Empty values** are written as `output.items_csv.null_value`: `None` in the example config, as in cHQ's sample, or blank by default.

## Keeping passwords out of files

On a desktop or server with an OS credential store, install the `keyring` extra and save each password once. The tool reads the stored password whenever its environment variable is unset:

| Password | Environment variable | Keyring service | Keyring username |
|---|---|---|---|
| FOLIO service account | `FOLIO_PASSWORD` | `folio-chq-folio` | `folio.username` |
| collectionHQ SFTP | `SFTP_PASSWORD` | `folio-chq-sftp` | `delivery.sftp.username` |

```bash
pip install 'folio-chq-extract[keyring]'
keyring set folio-chq-folio <FOLIO service account username>   # prompts for the password; nothing is echoed
keyring set folio-chq-sftp <your cHQ username>
folio-chq check            # says where the FOLIO password came from, then tests the login and permissions
folio-chq check --sftp     # logs in and verifies the host key; uploads nothing
```

On Windows this is Windows Credential Manager, encrypted for your user account. A scheduled task must run as the same user. In Docker or CI, use environment variables or secrets instead.

If your cHQ account can only upload (it can't list, stat or rename files), set `delivery.sftp.upload_mode: direct`.

## Scheduling

Pick whichever fits your institution. Most FOLIO hosts only accept API traffic from known networks, so run the tool somewhere that can reach your FOLIO.

**cron (Linux server):**
```cron
# 02:15 every Sunday
15 2 * * 0  cd /opt/folio-chq && . ./.env && /opt/folio-chq/venv/bin/folio-chq -c config.yaml run >> out/cron.log 2>&1
```

**Docker:**
```bash
docker build -t folio-chq-extract .
docker run --rm -v "$PWD/config.yaml:/app/config.yaml:ro" -v folio-chq-data:/app/data -v "$PWD/out:/app/out" \
  -e FOLIO_PASSWORD -e SFTP_PASSWORD folio-chq-extract run
```

Keep the `data/` volume between runs: it holds the cache that makes incremental updates possible.

**systemd timer** and **GitHub Actions** examples are in [`deploy/`](deploy/). GitHub-hosted runners only work if your FOLIO accepts traffic from the public internet. A self-hosted runner inside your network avoids that restriction.

## Development

```bash
pip install -e '.[dev]'
pytest           # runs end to end against an in-process mock FOLIO
ruff check .
```

Project status, open questions and next steps: [docs/HANDOFF.md](docs/HANDOFF.md). Notes for AI coding assistants: [CLAUDE.md](CLAUDE.md).

Contributions are welcome, especially reports of what your collectionHQ implementation asked for. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
