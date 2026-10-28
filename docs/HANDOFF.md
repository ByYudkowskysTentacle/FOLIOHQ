# Handoff: status and next steps

_Last updated: 27 October 2026, when the repository became the home of the `chq-academic` recipe._

## Where things stand

On 27 Oct 2026 this repository (then FOLIOHQ; renamed cHQ FOLIO Exchange Recipe on 28 Oct 2026) changed from a tool into the home of the **collectionHQ Academic recipe for [FOLIO-Exchange](https://github.com/ByYudkowskysTentacle/FOLIO-Exchange)** and its documentation. The first library's go-live now runs on FOLIO-Exchange. The original tool, `folio-chq-extract`, moved to `legacy/` and stays installable and tested as a fallback until FOLIO-Exchange makes its first real delivery.

**Nothing has been delivered to collectionHQ yet, and neither tool has run against the library's own tenant.** The collectionHQ SFTP login is confirmed (see below).

| Piece | State |
| --- | --- |
| Recipe `chq-academic` 1.0.0 | Reproduces the layout collectionHQ gave in Oct 2026. Validated by FOLIO-Exchange, and byte-identical to the legacy tool's output on the mock FOLIO (checked in CI). FOLIO-Exchange ships the same file. |
| FOLIO-Exchange | 0.1.0.dev0, unreleased; installs from GitHub. 177 offline tests. Run on 26 Oct 2026 against FOLIO's public Eureka Snapshot system: `check`, a full sync of 10,000 MARC records in 30 seconds, a held first delivery, `release`, then a delta run of under 4 seconds. Its own status is in its `docs/notes.md`. |
| Legacy tool | 30 offline tests. Smoke-tested on 23 Oct 2026 against FOLIO's Sunflower-on-Okapi and Eureka Snapshot systems; every file parsed, and every item row linked to a bib. |
| Docs | [setup.md](setup.md) (the route to go live), [layout.md](layout.md) (what collectionHQ receives), [the recipe's notes](../recipes/chq-academic/README.md) (how to change it). |

## Requirements as given by the library

- cHQ accepts CSV or MARC, or both. Full MARC is ideal, and the data may be split across files.
- The item file needs: **Barcode, Material Type, Last Circ Date, Status, Created Date, Location, Call Number.** The library uses LC classification.
- The connector can be any identifier, as long as it is unique and appears in both the bib file and the item data.
- The project should be open source, hosted on GitHub, and usable by other libraries.

## collectionHQ Academic file spec (from cHQ's head of implementation, Oct 2026)

cHQ sent the item fields its Academic product receives (the Library of Michigan layout) and a sample bib and item file. The recipe reproduces that layout; [layout.md](layout.md) describes it column by column.

- **Fields cHQ uses:** Bib record ID, Barcode, Material_type, Last_circ_date, Number of loans, Number of renewals, Status, Created_date, Location, Item_level_call_number.
- **Link:** `Bib record ID` is the FOLIO instance UUID. It matches the bib's 999 ff $i (which FOLIO's SRS writes), not 001.
- **Format:** pipe-delimited with a header row, and `None` for empty values. The sample bib has no 949 item fields.
- **Last_circ_date** is the checkout date. In the sample the loan was returned two months later, and that date is in Loan_return_date.
- **Samples get mangled in transit.** The sample `.marc` arrived with its field and subfield separators turned into newlines and ` $`, so no MARC reader could open it. Ask for vendor files zipped.

## Open questions for collectionHQ (ask before go-live)

The general list, for any library, is in [layout.md](layout.md#confirm-with-collectionhq). For the first library:

1. **Folder:** which folder on the server bibs and items go in (`delivery.remote_dir`). Not `holds` or `transactions`, which look like other feeds.
2. **Host key:** confirm RSA `SHA256:qt5HxgZ6ktlwhFUUAwdjMZlL2KkAbKXhy2TsRxWoITI`, which was read from the server, not received from cHQ.
3. **Cadence:** weekly or monthly, and is a full snapshot each time OK?
4. **PSV details:** the date format (we write `2022-06-25 12:23:54`, UTC, no fractions or offset), `None` or blank for empty values, `Name [code]` for Location, the effective call number for Item_level_call_number, and any file naming rules.
5. **Bibs and files:** are 949 item fields unwanted, as the sample suggests? Should files be compressed?

## collectionHQ SFTP (settled 26 Oct 2026)

- **Host:** `sftp.us.collectionhq.com`, port 22 (AWS Transfer Family). `ftp.collectionhq.com` is plain FTP only.
- **Account:** a password service account, described as upload-only, so the recipe uses `upload_mode: direct`. Listing the login folder works; it holds `.bash_logout`, `.bashrc`, `.profile`, `.ssh`, `holds`, `transactions`.
- **Login test:** `folio-chq check --sftp` succeeded on 26 Oct 2026. The password is in Windows Credential Manager on the setup PC under the legacy tool's name (`folio-chq-sftp`). FOLIO-Exchange keeps its own entry, so `folio-exchange init` (or `secret set chq`) stores it again.

## Questions for the library

- **FOLIO setup:** hosting (EBSCO, Index Data, self-hosted), release, and the tenant ID. The tenant is on Eureka. Is the library in an ECS consortium? If so, set `srs_include_shared: true`.
- **Service account:** a read-only account with the permissions in [setup.md](setup.md#from-your-folio-administrator-or-hosting-provider).
- **Migrated data:** were legacy circulation counts or created dates stored in item notes during migration? If so, which note types?
- **Filters:** which locations or statuses to leave out (for example e-resource locations).
- **Where it runs:** the library PC that holds the keyring entries, with the hourly scheduled task. Who gets failure alerts (email, or a Slack or Teams webhook)?

## Next steps (in order)

1. **Dry run against the library's tenant** with FOLIO-Exchange: [setup.md](setup.md) steps 1 to 4. The operator runs it; the password goes from their keyboard into Windows Credential Manager and is never shared. Spot-check about 20 items against the FOLIO UI, and note how long the first full sync takes.
2. **Send cHQ a sample** and the layout page (`folio-exchange recipes summary chq`), and settle the open questions above. Adjust the feed file; recipe changes should be rare.
3. **First delivery:** `run chq`, then `release chq` once cHQ has confirmed the folder and host key. cHQ accepting it is gate 1 of the FOLIO-Exchange roadmap.
4. **Schedule** the hourly task (`folio-exchange schedule`) on the library PC, as the user that holds the Credential Manager entries, and set up alerts.
5. **Retire the legacy tool** once cHQ has accepted a delivery from FOLIO-Exchange: remove `legacy/`, `tests/test_parity.py` and the legacy CI job, and keep a tag on the last commit that has it.
6. **Community:** add issue templates, and post to the FOLIO community (the Reporting SIG and the #reporting Slack channel), since other cHQ libraries may help confirm the layout.

**Fallback.** If FOLIO-Exchange is blocked when the library is ready to deliver, the legacy tool sends the same files: see [legacy/README.md](../legacy/README.md).

## Ideas and backlog (not started)

- Add cHQ's original sample files under `recipes/chq-academic/samples/` if cHQ agrees they can be published, so FOLIO-Exchange's preview checks a feed's header row against them.
- Compressed output (gzip or zip), if cHQ wants it. It needs a FOLIO-Exchange feature first.
- Check-in history (`/check-in-storage/check-ins`) to count in-house use: a new field in FOLIO-Exchange, then a new major recipe version.
- Bound-with support (`/inventory-storage/bound-with-parts`). Items currently report under their own holdings' instance.
