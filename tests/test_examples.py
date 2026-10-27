"""The example feed and the reference-system site load with FOLIO-Exchange, on this repository's recipe."""
import shutil
from pathlib import Path

from folio_exchange.cli import main as fx_main
from folio_exchange.config import load_site
from folio_exchange.recipe import RecipeLibrary, load_feed

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "recipes"


def test_example_feed_loads(tmp_path):
    feed = load_feed(ROOT / "examples" / "feeds" / "chq.yaml", RecipeLibrary([RECIPES]), tmp_path)
    assert feed.recipe.path.parent == RECIPES / "chq-academic"
    assert feed.delivery["host"] == "sftp.us.collectionhq.com" and feed.delivery["upload_mode"] == "direct"


def test_reference_site_uses_this_repositorys_recipes():
    site = load_site(ROOT / "examples" / "reference-eureka")
    assert site.recipe_dirs[0].resolve() == RECIPES
    feed = load_feed(site.feeds_dir / "chq.yaml", RecipeLibrary(site.recipe_dirs), site.root)
    assert feed.recipe.path.parent.resolve() == RECIPES / "chq-academic" and not feed.delivers


def test_reference_site_runs_end_to_end(tmp_path, folio, monkeypatch):
    """The same commands as the site's comments, against the mock FOLIO instead of the public test system."""
    shutil.copytree(ROOT / "examples" / "reference-eureka", tmp_path / "examples" / "reference-eureka")
    shutil.copytree(RECIPES, tmp_path / "recipes")
    monkeypatch.setenv("FOLIO_URL", folio.url)
    monkeypatch.setenv("FOLIO_PASSWORD", "secret")   # what the mock FOLIO accepts
    site = tmp_path / "examples" / "reference-eureka"
    assert fx_main(["-s", str(site), "check"]) == 0
    assert fx_main(["-s", str(site), "run", "chq"]) == 0
    run = next((site / "out" / "chq").glob("2*"))
    assert sorted(p.suffix for p in run.iterdir()) == [".json", ".mrc", ".psv"]
