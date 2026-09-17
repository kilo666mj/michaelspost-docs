from pathlib import Path

import yaml

from scripts.site import family_path, generated_nav, homepage, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_is_valid_and_complete():
    catalog = load_catalog()
    assert len(catalog["families"]) == 4
    assert len(catalog["projects"]) == 15
    assert len({project["id"] for project in catalog["projects"]}) == 15


def test_all_documentation_paths_are_unique():
    catalog = load_catalog()
    paths = [project["docs_path"] for project in catalog["projects"]]
    assert len(paths) == len(set(paths))


def test_navigation_contains_every_project():
    catalog = load_catalog()
    nav = generated_nav(catalog)
    flattened = repr(nav)
    for project in catalog["projects"]:
        assert project["name"] in flattened
        assert project["docs_path"].strip("/") in flattened


def test_navigation_contains_cross_project_guides():
    nav = generated_nav(load_catalog())
    assert {
        "Guides": [
            {"Gate stack": "guides/gate-stack.md"},
            {"Agent tooling stack": "guides/agent-tooling.md"},
        ]
    } in nav


def test_each_family_maps_to_one_public_path():
    catalog = load_catalog()
    for family in catalog["families"]:
        projects = [project for project in catalog["projects"] if project["family"] == family["id"]]
        assert len({family_path(project) for project in projects}) == 1


def test_homepage_prioritizes_search_and_project_discovery():
    catalog = load_catalog()
    content = homepage(catalog)
    assert 'class="docs-search"' in content
    assert 'for="__search"' in content
    for project in catalog["projects"]:
        assert f'href="{project["docs_path"].strip("/")}/"' in content


def test_theme_uses_documentation_layout_and_system_aware_palettes():
    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text())
    features = config["theme"]["features"]
    assert "navigation.sections" in features
    assert "toc.follow" in features
    assert "navigation.tabs" not in features
    palettes = config["theme"]["palette"]
    assert [palette["scheme"] for palette in palettes] == ["docs-light", "docs-dark"]
    assert [palette["media"] for palette in palettes] == [
        "(prefers-color-scheme: light)",
        "(prefers-color-scheme: dark)",
    ]
