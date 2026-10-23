# Handoff: status and next steps

_Last updated: 23 October 2026 (v0.1.0, first commit)._

## Where things stand

v0.1.0 is feature-complete for the first use case. It has **not yet been run against the library's own FOLIO tenant or a real collectionHQ SFTP server.**

**Reference-environment smoke test (23 Oct 2026): passed on both Okapi and Eureka.** `check` and `run --no-deliver` succeeded against FOLIO's public Sunflower-on-Okapi and Eureka Snapshot environments, using the configs in `examples/`. Results:
- Okapi: 46 bibs (6 SRS, 40 generated) and 28 items.
- Eureka: 122 bibs (81 SRS, 41 generated) and 25 items.

On both, every file parsed with pymarc and leader/09 is `a`. Every CSV `Instance HRID` matches a MARC 001, and the 949 $a barcodes exactly match the CSV barcodes. Some items have no barcode, because the sample data has none. Created dates show the rebuild date, the same effect a migration has.

Verified so far:
- The FOLIO endpoint paths, response keys, field names, query parameters and permission names were checked against the folio-org source in Oct 2026 (see `CLAUDE.md`).
- 17 automated tests pass against an in-process mock FOLIO. They cover a full run, delta sync, deletion detection, the safety check, retries and re-login, a bad password, custom columns and split files, stale-MARC handling, MARC long-field truncation, legacy date time zones, two-phase SFTP upload and login retry.
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

## Open questions for collectionHQ (ask before go-live)

1. **Link field:** do they match bibs to items on MARC 001 (instance HRID) or on the 949 $a barcode? Is the 949 subfield layout (`$a barcode $b item HRID $c call no. $l location code $t material type $s status`) acceptable, or do they want a different tag or subfields? This is configurable in `output.marc`.
2. **CSV format:** delimiter, date format, header names, and whether they need extra fields (for example YTD checkouts or loan type). Run `folio-chq fields` for what's available.
3. **SFTP:** host, port, username, auth method (key or password), remote folder, the host key fingerprint, and whether files should be compressed.
4. **Cadence:** weekly or monthly, and is a full file each time OK? The tool always sends a complete snapshot built from the cache.
5. **"Last Circ Date":** last checkout (the current default), or any circulation activity (`extract.last_circ_date_from: any`)?

## Questions for the library

- **FOLIO setup:** hosting (EBSCO, Index Data, self-hosted), release, Okapi or Eureka, and the tenant ID. Is the library in an ECS consortium? If so, set `srs_include_shared: true`.
- **Service account:** create a read-only service account with the permissions listed in the README.
- **Migrated data:** were legacy circulation counts or created dates stored in item notes during migration? If so, give the note type names and set them under `legacy:`.
- **Filters:** which locations or statuses to exclude (for example e-resource locations, Withdrawn, On order).
- **Where it runs:** a campus server (cron or systemd), Docker, or a self-hosted GitHub runner. Who gets failure alerts (a Slack or Teams webhook)?

## Suggested next steps (in order)

1. ~~**Try a FOLIO reference environment.**~~ Done on 23 Oct 2026 (see above). To repeat it, run `FOLIO_PASSWORD=admin folio-chq -c examples/reference-okapi.yaml run --no-deliver`, or the same with `reference-eureka.yaml`. Current URLs and demo logins: https://folio-org.atlassian.net/wiki/x/9oCeHg.
2. **Run against the library's tenant** with `--no-deliver`. Spot-check about 20 items against the FOLIO UI: last checkout, status, location, call number, counts. Note how long the first full sync takes.
3. **Send cHQ a sample** and settle the open questions above. Adjust `config.yaml`; code changes should rarely be needed.
4. **Build and test the Docker image** (`docker build -t folio-chq-extract .`), and pick a scheduling option from `deploy/`.
5. **Go live:** set `delivery.method: sftp`, pin `host_key_fingerprint`, and set up the webhook.
6. **Open-source polish** when ready to publish:
   - Make the repo public.
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
