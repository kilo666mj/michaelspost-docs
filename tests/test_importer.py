import json
import subprocess
from pathlib import Path

import pytest

from scripts.importer import ImportFailure, clean_repo_path, import_all


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def create_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "source"
    repository.mkdir()
    run("git", "init", "-b", "main", cwd=repository)
    run("git", "config", "user.name", "Docs Test", cwd=repository)
    run("git", "config", "user.email", "docs@example.com", cwd=repository)
    (repository / "docs" / "images").mkdir(parents=True)
    (repository / "README.md").write_text(
        "# Example\n\n"
        "Read the [guide\npage](docs/guide.md), view ![diagram](docs/images/diagram.png), "
        "or inspect the [license](LICENSE).\n\n"
        "[![License](https://img.shields.io/badge/license-test-blue.svg)](LICENSE)\n"
    )
    (repository / "docs" / "guide.md").write_text(
        "# Guide\n\nReturn to the [README](../README.md#example).\n"
    )
    (repository / "docs" / "images" / "diagram.png").write_bytes(b"synthetic-png")
    (repository / "LICENSE").write_text("test license\n")
    run("git", "add", ".", cwd=repository)
    run("git", "commit", "-m", "Add documentation", cwd=repository)
    return repository, run("git", "rev-parse", "HEAD", cwd=repository)


def catalog(repository: Path) -> dict:
    return {
        "version": 1,
        "families": [],
        "projects": [
            {
                "id": "example",
                "name": "Example",
                "family": "test",
                "kind": "application",
                "status": "active",
                "summary": "Example project.",
                "repository": str(repository),
                "docs_path": "/test/example/",
                "source": {"ref": "main", "readme": "README.md", "roots": ["docs"]},
            }
        ],
    }


def test_import_all_resolves_commit_rewrites_links_and_records_manifest(tmp_path):
    repository, commit = create_repository(tmp_path)
    destination = tmp_path / "site"
    destination.mkdir()

    manifest = import_all(catalog(repository), destination, tmp_path / "cache")

    landing = (destination / "test/example/index.md").read_text()
    guide = (destination / "test/example/docs/guide.md").read_text()
    assert landing.count("# Example") == 1
    assert "docs/guide.md" in landing
    assert "docs/images/diagram.png" in landing
    assert f"{repository}/blob/{commit}/LICENSE" in landing
    assert "](LICENSE)" not in landing
    assert "../index.md#example" in guide
    assert (destination / "test/example/docs/images/diagram.png").read_bytes() == b"synthetic-png"
    assert manifest["projects"][0]["resolved_commit"] == commit
    assert manifest["projects"][0]["requested_ref"] == "main"
    assert len(manifest["projects"][0]["pages"]) == 2
    on_disk = json.loads((destination / "build-manifest.json").read_text())
    assert on_disk["projects"] == manifest["projects"]


def test_missing_configured_content_fails_clearly(tmp_path):
    repository, _ = create_repository(tmp_path)
    configured = catalog(repository)
    configured["projects"][0]["source"]["readme"] = "MISSING.md"
    destination = tmp_path / "site"
    destination.mkdir()

    with pytest.raises(ImportFailure, match="configured source file is missing: MISSING.md"):
        import_all(configured, destination, tmp_path / "cache")


def test_missing_local_image_fails_clearly(tmp_path):
    repository, _ = create_repository(tmp_path)
    (repository / "README.md").write_text("# Example\n\n![missing](docs/images/missing.png)\n")
    run("git", "add", "README.md", cwd=repository)
    run("git", "commit", "-m", "Reference missing image", cwd=repository)
    destination = tmp_path / "site"
    destination.mkdir()

    with pytest.raises(ImportFailure, match="references a missing image"):
        import_all(catalog(repository), destination, tmp_path / "cache")


@pytest.mark.parametrize("value", ["../secret.md", "/absolute.md", "docs\\secret.md", ""])
def test_unsafe_repository_paths_are_rejected(value):
    with pytest.raises(ImportFailure, match="repository path"):
        clean_repo_path(value)
