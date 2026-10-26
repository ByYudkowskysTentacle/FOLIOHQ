# Changelog

## Unreleased
- Matches the PSV item extract collectionHQ Academic receives, as given by cHQ's implementation team. `config.example.yaml` now uses its 20 columns and headers, pipe delimiter, `.psv` extension, `None` for empty values and `YYYY-MM-DD HH:MM:SS` dates.
- The bib-to-item link cHQ uses is `Bib record ID` = MARC 999 ff $i = FOLIO instance UUID. Every bib now gets a 999 ff $i that matches its instance (reported as `marc_999_corrected` when it had to be fixed).
- New item fields: `item_identifier`, `number_of_pieces`, `item_level_call_number`, `last_return_date`, `location_name_code`.
- New options: `output.marc.embed_items` (default `true`; the example turns it off, because cHQ's sample bib has no item fields), `output.items_csv.file_extension` (default `csv`) and `output.items_csv.null_value` (default blank).
- Delivery sends the item file with whatever extension is configured.

## 0.1.0
- First release: MARC bibs from SRS (generated MARC for FOLIO-source instances) with embedded 949 item fields; configurable items CSV; incremental sync with SQLite cache; SFTP delivery; safety check; webhook notifications.
