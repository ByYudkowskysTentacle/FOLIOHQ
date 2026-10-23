# Contributing

Thanks for helping. Libraries often find gaps first, so issues and pull requests from FOLIO sites are very welcome.

- **Bug reports:** include your FOLIO release (for example Sunflower or Trillium), whether you run Okapi or Eureka, and the `run-report.json` from the failed run (remove anything sensitive first).
- **collectionHQ requirements:** if your collectionHQ implementation asked for a field or layout the tool can't produce, open an issue describing it. New fields go in `src/folio_chq/fields.py`.
- **Code:** run `pip install -e '.[dev]'`, then `ruff check .` and `pytest`. Tests run against the mock FOLIO in `tests/mock_folio.py`. Extend it when you add API calls.
- Never commit real configuration, credentials, or patron data.
