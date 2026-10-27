# Contributing

Thanks for helping. Libraries often find gaps first, so issues and pull requests from FOLIO sites are very welcome.

- **What collectionHQ asked for:** if your collectionHQ implementation asked for a column, format or file layout the recipe doesn't produce, open an issue describing it, and say whether the request is for your library only or for every library. A local difference is a setting in your feed file; [docs/setup.md](docs/setup.md#5-agree-the-files-with-collectionhq) shows where.
- **Recipe changes:** follow [the recipe's notes](recipes/chq-academic/README.md#making-a-new-version). A change collectionHQ would notice is a new major version.
- **Docs:** corrections to the setup guide or the layout are welcome, especially from a library that has just gone through them.
- **Problems running FOLIO-Exchange:** open the issue in [FOLIO-Exchange](https://github.com/ByYudkowskysTentacle/FOLIO-Exchange/issues). Include your FOLIO release (for example Sunflower or Trillium), whether you run Okapi or Eureka, and the `run-report.json` from the failed run, with anything sensitive removed.
- **Tests:** `pip install -r requirements-dev.txt`, then `ruff check .` and `pytest -q`. They run offline against a mock FOLIO.
- **The legacy tool** (`legacy/`) takes bug fixes only, with a regression test.
- Never commit real settings files, credentials or patron data.
