# Changelog

folio-chq-extract, the legacy tool. The collectionHQ Academic recipe for FOLIO-Exchange has its own changelog inside each recipe file, and the repository's in `../CHANGELOG.md`.

## Unreleased
- Moved to `legacy/` when this repository (then FOLIOHQ) became the home of the `chq-academic` recipe for FOLIO-Exchange. Install with `pip install "folio-chq-extract @ git+https://github.com/ByYudkowskysTentacle/cHQ-FOLIO-Exchange-Recipe.git#subdirectory=legacy"`. Behaviour is unchanged.
- Matches the PSV item extract collectionHQ Academic receives, as given by cHQ's implementation team. `config.example.yaml` now uses its 20 columns and headers, pipe delimiter, `.psv` extension, `None` for empty values and `YYYY-MM-DD HH:MM:SS` dates.
- The bib-to-item link cHQ uses is `Bib record ID` = MARC 999 ff $i = FOLIO instance UUID. Every bib now gets a 999 ff $i that matches its instance (reported as `marc_999_corrected` when it had to be fixed).
- New item fields: `item_identifier`, `number_of_pieces`, `item_level_call_number`, `last_return_date`, `location_name_code`.
- New options: `output.marc.embed_items` (default `true`; the example turns it off, because cHQ's sample bib has no item fields), `output.items_csv.file_extension` (default `csv`) and `output.items_csv.null_value` (default blank).
- Delivery sends the item file with whatever extension is configured.
- `folio-chq check --sftp` tests the SFTP login and host key, then lists the remote folder, without uploading anything. Upload-only accounts that can't list are reported as OK.
- `delivery.sftp.upload_mode: direct` uploads straight to the final file names with no stat or rename, for upload-only accounts. The default is still `staged`.
- Optional `[keyring]` extra: when `FOLIO_PASSWORD` or `SFTP_PASSWORD` is unset, that password is read from the OS credential store (services `folio-chq-folio` and `folio-chq-sftp`, keyed by the configured username). `folio-chq check` reports where the password came from, without showing it.

## 0.1.0
- First release: MARC bibs from SRS (generated MARC for FOLIO-source instances) with embedded 949 item fields; configurable items CSV; incremental sync with SQLite cache; SFTP delivery; safety check; webhook notifications.
