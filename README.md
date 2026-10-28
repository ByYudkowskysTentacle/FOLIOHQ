# cHQ FOLIO Exchange Recipe: collectionHQ Academic for FOLIO

What a [FOLIO](https://www.folio.org/) library needs to send its catalogue and circulation data to **collectionHQ Academic** on a schedule, with [FOLIO-Exchange](https://github.com/ByYudkowskysTentacle/FOLIO-Exchange). It holds the shared `chq-academic` recipe, a step-by-step setup guide, and a description of the files collectionHQ receives. This repository was called FOLIOHQ until 28 October 2026; links to the old name still lead here.

> This is a community project. It is not affiliated with or endorsed by collectionHQ or the FOLIO project. Confirm the file layout with your collectionHQ implementation contact before you go live.

## What collectionHQ receives

Each run sends two files over SFTP:

| File | Contents |
| --- | --- |
| `chq_bibs_YYYYMMDD.mrc` | One MARC 21 record per title (UTF-8, ISO 2709): FOLIO's own record from Source Record Storage, or a brief record built from the instance when there is none |
| `chq_items_YYYYMMDD.psv` | One pipe-delimited row per item, 20 columns: barcode, status, location, call number, material type, created date, last checkout and return, loan and renewal counts, and more |

collectionHQ links each item to its title through the FOLIO instance UUID, which is in MARC **999 ff $i** and in the item file's **Bib record ID** column. [docs/layout.md](docs/layout.md) describes every column and where in FOLIO it comes from.

## How the pieces fit

| Piece | What it does | Where it lives |
| --- | --- | --- |
| FOLIO-Exchange | Reads FOLIO, keeps a local cache, builds the files, checks them, holds the first delivery for review, sends them and records every run | [its repository](https://github.com/ByYudkowskysTentacle/FOLIO-Exchange), installed on a PC or server inside the library's network |
| The `chq-academic` recipe | Describes collectionHQ Academic's files: the columns, formats, link and checks | [recipes/chq-academic/](recipes/chq-academic/) here; FOLIO-Exchange ships a copy |
| A library's feed file | Holds the library's own choices: locations to leave out, legacy item notes, the SFTP account, the schedule | in the library's site folder; [examples/feeds/chq.yaml](examples/feeds/chq.yaml) is a commented example |

A recipe update never touches a library's feed file, and a change collectionHQ would notice is a new major version that waits for the library to accept it.

## Getting started

1. **Try it on FOLIO's public test system**, with no library account: [examples/reference-eureka/site.yaml](examples/reference-eureka/site.yaml) has the commands.
2. **Set it up for your library** with the [setup guide](docs/setup.md). In short, after installing FOLIO-Exchange:

   ```powershell
   folio-exchange init C:\FOLIO-Exchange\mylibrary     # guided: FOLIO account, the recipe, filters, SFTP, alerts
   folio-exchange -s C:\FOLIO-Exchange\mylibrary run chq --no-deliver   # build the files and check them
   folio-exchange -s C:\FOLIO-Exchange\mylibrary run chq                # the first delivery waits for you
   folio-exchange -s C:\FOLIO-Exchange\mylibrary release chq            # send it once you have checked it
   folio-exchange -s C:\FOLIO-Exchange\mylibrary schedule               # prints the command that schedules it
   ```

## Status

- **The recipe** (1.0.0) reproduces the layout collectionHQ's implementation team gave in October 2026. Tests check that FOLIO-Exchange writes it byte for byte the same as the legacy tool.
- **FOLIO-Exchange** is in development (0.1.0.dev0) and installs from GitHub. It has run against FOLIO's public Eureka test system; the legacy tool ran against both the Okapi and Eureka ones.
- **Nothing has been delivered to collectionHQ yet**, and neither tool has run against a library's own tenant. Status, open questions and next steps are in [docs/HANDOFF.md](docs/HANDOFF.md).

## The legacy tool

[legacy/](legacy/) holds `folio-chq-extract`, the one-vendor tool this repository started as. It writes the same two files, and stays installable and tested as a fallback until FOLIO-Exchange makes its first real delivery. New setups should use FOLIO-Exchange; [legacy/README.md](legacy/README.md#moving-to-folio-exchange) explains how to move.

## Repository layout

```
recipes/chq-academic/   the recipe: one file per version, plus notes on changing it
examples/               a commented feed file, and a site that runs on FOLIO's public test system
docs/                   the setup guide, the file layout, and status and open questions
tests/                  the recipe on FOLIO-Exchange, and byte parity with the legacy tool
legacy/                 folio-chq-extract, the original tool, with its own tests
```

## Development

From the repository root:

```bash
pip install -r requirements-dev.txt   # FOLIO-Exchange from GitHub, the legacy tool, pytest and ruff
pytest -q                             # the recipe tests; they run offline against a mock FOLIO
ruff check .
```

The legacy tool's own tests run from `legacy/` (see [legacy/README.md](legacy/README.md#development)). Notes for AI coding assistants are in [CLAUDE.md](CLAUDE.md).

Contributions are welcome, especially reports of what your collectionHQ implementation asked for. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
