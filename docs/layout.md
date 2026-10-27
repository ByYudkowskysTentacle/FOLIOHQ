# The collectionHQ Academic file layout

_Recipe `chq-academic` 1.0.0. Source: collectionHQ's implementation team, Oct 2026 (the Library of Michigan layout). `folio-exchange recipes summary chq` prints the same layout, with your library's own settings, as a page to send collectionHQ._

Each delivery is a complete snapshot of the collection in two files. collectionHQ links them through the FOLIO instance UUID, which is in MARC **999 ff $i** of each bib and in the **Bib record ID** column of each item row.

| File | Format | One per |
| --- | --- | --- |
| `chq_bibs_YYYYMMDD.mrc` | MARC 21, ISO 2709, UTF-8 | title (FOLIO instance) with at least one item that goes out |
| `chq_items_YYYYMMDD.psv` | pipe-delimited text, UTF-8, header row | item |

`YYYYMMDD` is the run's date in UTC. `chq` is the feed's `file_prefix`.

## Bib file

- **The record:** FOLIO's own MARC from Source Record Storage for MARC-source instances (`MARC`, `CONSORTIUM-MARC`). Instances with no MARC record (`FOLIO`, `CONSORTIUM-FOLIO`, `LINKED_DATA` sources) get a brief record built from the instance, so no title is left out for want of MARC. It holds 001, 008, 010, 020, 022, 035, 050, 082, 100, 245, 250, 264, 300, 490, 700 and 999, as far as the instance has the data.
- **The link:** every record gets **001 = instance HRID** and **999 ff $i = instance UUID**. SRS already writes 999 ff $i; FOLIO-Exchange adds or corrects it where it is missing or wrong.
- **No item fields.** collectionHQ's sample bib has none, so items are not embedded, and any old 949 is removed from the record.
- **Size limits:** leader position 9 is `a` (UTF-8). A field over 9,999 bytes is shortened at a character boundary; a record over 99,999 bytes is left out of the bib file, and its items stay in the item file.

## Item file

Pipe (`|`) delimited, UTF-8 without a byte-order mark, Windows line ends (CR LF), one header row. A value is quoted only when it contains a pipe, a quote or a line break. Empty values are written as `None`, as in collectionHQ's sample; `0` stays `0`. Dates are written `YYYY-MM-DD HH:MM:SS` in the feed's time zone (UTC unless the feed's `options.timezone` says otherwise).

| # | Column | FOLIO-Exchange field | Where the value comes from in FOLIO |
| --- | --- | --- | --- |
| 1 | Bib record ID | `instance_id` | Instance UUID; the same value as the bib's 999 ff $i |
| 2 | Item record ID | `item_id` | Item UUID |
| 3 | Item record HRID | `item_hrid` | Item HRID |
| 4 | Item identifier | `item_identifier` | Item's `itemIdentifier`, often the old system's item number |
| 5 | Barcode | `barcode` | Item barcode; `None` when the item has none |
| 6 | Enumeration | `enumeration` | Item enumeration |
| 7 | Chronology | `chronology` | Item chronology |
| 8 | Item_level_call_number | `call_number` | The item's effective call number with prefix and suffix: its own call number, else the holdings record's |
| 9 | Volume | `volume` | Item volume |
| 10 | Created_date | `created_date` | When the item record was created, or a legacy note's date (see below) |
| 11 | Status | `status` | Item status name, such as Available or Checked out |
| 12 | Location | `location_name_code` | The item's effective location as `Name [code]`: its temporary location, else its permanent one, else the holdings record's location. The name is the location's discovery display name when it has one |
| 13 | Material_type | `material_type` | Material type name |
| 14 | Number_of_pieces | `number_of_pieces` | Item number of pieces |
| 15 | Copy_number | `copy_number` | Item copy number |
| 16 | Loan_name | `loan_type` | Permanent loan type name |
| 17 | Last_circ_date | `last_circ_date` | The most recent checkout recorded in FOLIO, or a legacy note's date if that is newer |
| 18 | Loan_return_date | `last_return_date` | The most recent return recorded in FOLIO |
| 19 | Number of loans | `loans_total` | Loans recorded in FOLIO, plus a legacy note's count |
| 20 | Number of renewals | `renewals_total` | Renewals across every FOLIO loan of the item |

collectionHQ uses Bib record ID, Barcode, Material_type, Last_circ_date, Number of loans, Number of renewals, Status, Created_date, Location and Item_level_call_number. The other columns are in the layout it receives from other libraries. A feed cannot remove Bib record ID, Barcode, Status or Material_type.

**Loans and patron data.** Loans are read only for the item, dates, renewal count and status. FOLIO keeps those after it anonymizes a loan, so anonymizing does not lower the counts. The borrower is dropped from each loan as it arrives and is never stored or sent.

**Migrated items.** A migration stamps every item with the migration date as its created date, and FOLIO keeps no loan history from the old system. If the migration kept those values in item notes, name the note types in the feed's `legacy` settings. The created-date note then replaces Created_date, the circulation-count note is added to Number of loans, and the last-checkout note is used when FOLIO has no newer checkout.

**Bound-with items** are reported under the instance their own holdings record belongs to.

## Which records go out

These are the recipe's defaults. A feed's `filters` can change any of them.

| Setting | Default | Meaning |
| --- | --- | --- |
| `include_suppressed_instances` | `false` | Leave out instances suppressed from discovery or staff-suppressed, with their items |
| `include_suppressed_items` | `false` | Leave out items suppressed from discovery |
| `include_items_without_barcode` | `true` | Send items with no barcode |
| `bibs_without_items` | `false` | Send a bib only when at least one of its items goes out |
| `exclude_item_statuses` | none | Item statuses to leave out; collectionHQ analyses every status |
| `include_location_codes` | all | Only these effective locations, when set |
| `exclude_location_codes` | none | Effective locations to leave out, such as online resources |

## Checks before a delivery

A run is blocked, and nothing is sent, when:

- the item count falls below 90% of the last delivery to the same destination (`checks.min_item_ratio`), or
- any item row has an empty Bib record ID, Status or Material_type.

The first delivery to a new destination, and the first on a new major version of the recipe, waits for a person to release it.

## Delivery

SFTP with a pinned host key, uploading each file straight to its final name (`upload_mode: direct`), because collectionHQ's accounts are described as upload-only. The host, account, folder and key are the library's own settings; [setup.md](setup.md) lists what is known about collectionHQ's server.

## Confirm with collectionHQ

The layout above is what collectionHQ's implementation team gave in October 2026. Before your first delivery, confirm with your own implementation contact:

- [ ] The folder on the SFTP server for bibs and items.
- [ ] The cadence (weekly or monthly) and that a full snapshot each time is right.
- [ ] Dates: their sample mixes `2022-06-25 12:23:54.249000` with `2024-05-29 16:13:07.512000+00:00`; FOLIO-Exchange writes `2022-06-25 12:23:54`, without fractions or offset.
- [ ] Empty values: `None`, as in their sample, or blank.
- [ ] Location as `Name [code]`, as in their sample.
- [ ] Item_level_call_number as the effective call number (item, else holdings), rather than only the item record's own, which leaves many items blank.
- [ ] File names: their sample was `<barcode>_bib.marc` and `<barcode>_item_with_headers.psv`.
- [ ] That no 949 item fields are wanted in the bibs, and whether they want the files compressed.
- [ ] The server's host key fingerprint.

A change any of these needs is a local setting (the feed's `outputs`, `filters` or `delivery`), except one collectionHQ wants from every library, which belongs in a new version of the recipe.
