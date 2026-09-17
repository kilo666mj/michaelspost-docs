from scripts.site import family_path, generated_nav, load_catalog


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
