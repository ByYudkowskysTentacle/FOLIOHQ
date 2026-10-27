"""The recipes here load and validate with FOLIO-Exchange, and FOLIO-Exchange's bundled copies match them."""
from pathlib import Path

import pytest
from folio_exchange.config import BUNDLED_RECIPES
from folio_exchange.recipe import RecipeLibrary, load_recipe_file

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "recipes"
RECIPE_FILES = sorted(RECIPES.glob("*/*.yaml"))


def test_chq_academic_is_here():
    assert RECIPES / "chq-academic" / "1.0.0.yaml" in RECIPE_FILES


@pytest.mark.parametrize("path", RECIPE_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_recipe_validates(path):
    recipe = load_recipe_file(path)           # every FOLIO-Exchange rule: fields, link, outputs, changelog
    assert recipe.data["patron_data"] == "none"


def test_library_resolves_from_this_repository():
    library = RecipeLibrary([RECIPES])
    assert library.problems() == []
    assert library.resolve("chq-academic@^1.0").path.parent == RECIPES / "chq-academic"


def test_bundled_copies_match_this_repository():
    """This repository is the source. Every file FOLIO-Exchange bundles for these recipes must be here, unchanged.

    A file only here is fine: a new version or note that no FOLIO-Exchange release carries yet."""
    shared = sorted(p for p in BUNDLED_RECIPES.iterdir() if (RECIPES / p.name).is_dir())
    assert shared, "FOLIO-Exchange bundles none of the recipes kept here"
    for folder in shared:
        for bundled in sorted(f for f in folder.rglob("*") if f.is_file()):
            name = bundled.relative_to(BUNDLED_RECIPES)
            ours = RECIPES / name
            assert ours.is_file(), f"FOLIO-Exchange bundles {name}, which is missing here"
            assert ours.read_bytes() == bundled.read_bytes(), f"FOLIO-Exchange's copy of {name} differs from this one"


def test_layout_doc_lists_every_column_in_order():
    """docs/layout.md is what libraries and collectionHQ read; it must describe the latest 1.x recipe exactly."""
    recipe = RecipeLibrary([RECIPES]).resolve("chq-academic@^1.0")
    items = next(o for o in recipe.data["outputs"] if o["format"] == "delimited")
    expected = [(c["header"], c["field"]) for c in items["columns"]]
    doc = (ROOT / "docs" / "layout.md").read_text(encoding="utf-8")
    rows = [line.split("|")[2:4] for line in doc.splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    assert [(header.strip(), field.strip().strip("`")) for header, field in rows] == expected
    assert f"`chq-academic` {recipe.version_str}" in doc
