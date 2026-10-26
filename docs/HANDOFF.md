# Handoff: status and next steps

_Last updated: 26 October 2026 (v0.1.0 plus the cHQ Academic layout, unreleased)._

## Where things stand

v0.1.0 is feature-complete for the first use case. It has **not yet been run against the library's own FOLIO tenant, and nothing has been uploaded to collectionHQ yet.** The SFTP login is confirmed (see below).

**Reference-environment smoke test (23 Oct 2026): passed on both Okapi and Eureka.** `check` and `run --no-deliver` succeeded against FOLIO's public Sunflower-on-Okapi and Eureka Snapshot environments, using the configs in `examples/`. Results:
- Okapi: 46 bibs (6 SRS, 40 generated) and 28 items.
- Eureka: 122 bibs (81 SRS, 41 generated) and 25 items.

On both, every file parsed with pymarc and leader/09 is `a`. Every CSV `Instance HRID` matches a MARC 001, and the 949 $a barcodes exactly match the CSV barcodes. Some items have no barcode, because the sample data has none. Created dates show the rebuild date, the same effect a migration has.

Verified so far:
- The FOLIO endpoint paths, response keys, field names, query parameters and permission names were checked against the folio-org source in Oct 2026 (see `CLAUDE.md`).
- 26 automated tests pass against an in-process mock FOLIO. They cover the cHQ Academic PSV layout and the 999 ff $i link, the read-only SFTP check, direct (upload-only) SFTP mode, the keyring password, a full run, delta sync, deletion detection, the safety check, retries and re-login, a bad password, custom columns and split files, stale-MARC handling, MARC long-field truncation, legacy date time zones, two-phase SFTP upload and login retry.
- An independent code review found eight defects, and all are fixed with regression tests:
  - fields over 9,999 bytes
  - delivering a partial run
  - login not retried
  - legacy date off-by-one
  - stale MARC in the cache
  - CSV rows dropped for oversize bibs
  - a non-atomic SFTP pair
  - unsorted reference-data paging
- Clean `pip install .` in a fresh virtualenv works. The Dockerfile has **not** been built yet (no Docker daemon was available).
- The build step was timed on a synthetic 100k-bib / 200k-item cache: about 30 seconds.

## Requirements as given by the library

- cHQ accepts CSV or MARC, or both. Full MARC is ideal, and the data may be split across files.
- The item file needs: **Barcode, Material Type, Last Circ Date, Status, Created Date, Location, Call Number.** The library uses LC classification.
- The connector can be any identifier, as long as it is unique and appears in both the bib file and the item data.
- The project should be an open-source, GitHub-hosted tool other libraries can use.

## collectionHQ Academic file spec (from cHQ's head of implementation, Oct 2026)

cHQ sent the item fields its Academic product receives (the Library of Michigan layout) and a sample bib and item, `examples/30000010867376_bib.marc` and `examples/30000010867376_item_with_headers.psv`. `config.example.yaml` now reproduces that layout.

- **Fields cHQ uses:** Bib record ID, Barcode, Material_type, Last_circ_date, Number of loans, Number of renewals, Status, Created_date, Location, Item_level_call_number.
- **Full PSV column list:** Bib record ID, Item record ID, Item record HRID, Item identifier, Barcode, Enumeration, Chronology, Item_level_call_number, Volume, Created_date, Status, Location, Material_type, Number_of_pieces, Copy_number, Loan_name, Last_circ_date, Loan_return_date, Number of loans, Number of renewals.
- **Link:** `Bib record ID` is the FOLIO instance UUID. It matches the bib's 999 ff $i (which FOLIO's SRS writes), not 001.
- **Format:** pipe-delimited with a header row, and `None` for empty values. The sample bib has no 949 item fields.
- **Last_circ_date** is the checkout date. In the sample the loan was returned two months later, and that date is in Loan_return_date. So the `checkout` default is right.

## Open questions for collectionHQ (ask before go-live)

1. ~~**Link field.**~~ Answered: `Bib record ID` = 999 ff $i (instance UUID). Still to confirm: are 949 item fields unwanted? The example config turns them off to match the sample.
2. **PSV details.** The columns and headers are answered. Still to confirm:
   - **Dates:** the sample mixes `2022-06-25 12:23:54.249000` with `2024-05-29 16:13:07.512000+00:00`. We write `2022-06-25 12:23:54` (UTC, no fractions or offset). Is that OK?
   - **Empty values:** is `None` required, or is blank fine?
   - **Location:** we send "Name [code]", as in the sample. Is that what they expect from every library?
   - **Item_level_call_number:** we send the effective call number (item, else holdings). Should it be the item record's own call number only, even if that leaves many items blank?
   - **File names:** the sample is `<barcode>_bib.marc` / `<barcode>_item_with_headers.psv`; we send `chq_bibs_YYYYMMDD.mrc` / `chq_items_YYYYMMDD.psv`. Any naming rules?
3. **SFTP.** The connection is settled, and the login was tested with `folio-chq check --sftp` on 26 Oct 2026:
   - **Host:** `sftp.us.collectionhq.com`, port 22 (AWS Transfer Family). The other host cHQ listed, `ftp.collectionhq.com`, is plain FTP only.
   - **Account:** a password service account, described as upload-only. Its password is in Windows Credential Manager (`folio-chq-sftp`) on the setup PC, and `config.yaml` uses `upload_mode: direct`.
   - **Host key:** RSA `SHA256:qt5HxgZ6ktlwhFUUAwdjMZlL2KkAbKXhy2TsRxWoITI`. This was read from the server, not from cHQ, so ask them to confirm it.
   - **Login folder contents:** `.bash_logout`, `.bashrc`, `.profile`, `.ssh`, `holds`, `transactions`. Listing works, so the account is not strictly upload-only.
   - **Still to ask:**
     - Which folder should the bib and item files go in (`remote_dir`)? Not `holds` or `transactions`, which look like other feeds.
     - Should files be compressed?
     - Does their pickup ignore partial uploads? This only matters if we switch to `staged` mode.
4. **Cadence:** weekly or monthly, and is a full file each time OK? The tool always sends a complete snapshot built from the cache.
5. ~~**"Last Circ Date."**~~ Answered by the sample: last checkout, the default.

## Questions for the library

- **FOLIO setup:** hosting (EBSCO, Index Data, self-hosted), release, Okapi or Eureka, and the tenant ID. Is the library in an ECS consortium? If so, set `srs_include_shared: true`.
- **Service account:** create a read-only service account with the permissions listed in the README.
- **Migrated data:** were legacy circulation counts or created dates stored in item notes during migration? If so, give the note type names and set them under `legacy:`.
- **Filters:** which locations or statuses to exclude (for example e-resource locations, Withdrawn, On order).
- **Where it runs:** a campus server (cron or systemd), Docker, or a self-hosted GitHub runner. Who gets failure alerts (a Slack or Teams webhook)?

## Suggested next steps (in order)

1. ~~**Try a FOLIO reference environment.**~~ Done on 23 Oct 2026 (see above). To repeat it, run `FOLIO_PASSWORD=admin folio-chq -c examples/reference-okapi.yaml run --no-deliver`, or the same with `reference-eureka.yaml`. Current URLs and demo logins: https://folio-org.atlassian.net/wiki/x/9oCeHg.
2. **Run against the library's tenant** with `--no-deliver`. Spot-check about 20 items against the FOLIO UI: last checkout, status, location, call number, counts. Note how long the first full sync takes.
3. **Send cHQ a sample** built with `config.example.yaml`'s layout and settle the remaining open questions above. Adjust `config.yaml`; code changes should rarely be needed.
4. **Build and test the Docker image** (`docker build -t folio-chq-extract .`), and pick a scheduling option from `deploy/`.
5. **Go live:** set `remote_dir` once cHQ confirms it, run as the Windows user that holds the Credential Manager entry (or use `SFTP_PASSWORD` on a server), and set up the webhook. The host and fingerprint are already set.
6. **Open-source polish** when ready to publish:
   - ~~Make the repo public.~~ Done on 23 Oct 2026.
   - Add issue templates.
   - Consider publishing to PyPI.
   - Post to the FOLIO community (the Reporting SIG and the #reporting Slack channel), since other cHQ libraries may help confirm the file spec.

## Ideas and backlog (not started)

- Optional check-in history (`/check-in-storage/check-ins`) to count in-house use.
- An option to compress output files (gzip or zip) if cHQ wants it.
- Email notification (SMTP) in addition to webhooks.
- Support for the bound-with relationship (`/inventory-storage/bound-with-parts`). Items currently report under their own holdings' instance.
- A `--dry-run` sample mode that writes the first N bibs and items, for quick previews to cHQ.
- A changes-only delivery mode, if cHQ ever asks for it.
