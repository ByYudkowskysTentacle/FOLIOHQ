# Changelog

Changes to this repository. Each recipe version's own changes are in its `changelog`, and the legacy tool's in `legacy/CHANGELOG.md`.

## 2026-10-27
- FOLIOHQ became the home of the collectionHQ Academic recipe for FOLIO-Exchange and its documentation.
- `recipes/chq-academic/1.0.0.yaml`: the recipe, the source of the copy FOLIO-Exchange ships, with notes on changing it.
- `docs/setup.md`: from nothing to a weekly delivery with FOLIO-Exchange. `docs/layout.md`: every file, column and check, and where each value comes from in FOLIO.
- `examples/feeds/chq.yaml`, a commented feed file, and `examples/reference-eureka/`, a site that runs on FOLIO's public Eureka test system.
- Tests: the recipe validated by FOLIO-Exchange, the examples run against a mock FOLIO, the layout doc and the shipped copy checked against the recipe, and byte parity with the legacy tool.
- `folio-chq-extract` moved to `legacy/`, unchanged, as a fallback until FOLIO-Exchange's first real delivery.
