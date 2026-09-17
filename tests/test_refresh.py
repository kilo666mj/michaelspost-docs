import datetime as dt
import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts import refresh


def configure_cache(monkeypatch, tmp_path: Path) -> None:
    cache = tmp_path / "refresh"
    monkeypatch.setattr(refresh, "CACHE", cache)
    monkeypatch.setattr(refresh, "LEASE", cache / "lease.json")
    monkeypatch.setattr(refresh, "CANDIDATE", cache / "candidate.json")
    monkeypatch.setattr(refresh, "ARCHIVE", cache / "site.zip")
    monkeypatch.setattr(refresh, "PUBLISHED", cache / "published.json")
    monkeypatch.setattr(refresh, "FAILURES", cache / "failures.json")


def test_source_state_ignores_build_time():
    manifest = {
        "site_built_at": "first",
        "projects": [
            {"id": "second", "resolved_commit": "b" * 40},
            {"id": "first", "resolved_commit": "a" * 40},
        ],
    }
    expected = {
        "site_commit": "c" * 40,
        "projects": {"second": "b" * 40, "first": "a" * 40},
    }
    assert refresh.source_state(manifest, "c" * 40) == expected
    manifest["site_built_at"] = "later"
    assert refresh.source_state(manifest, "c" * 40) == expected


def test_package_is_deterministic_and_has_root_entrypoint(tmp_path):
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text("<h1>Docs</h1>")
    (site / "assets" / "style.css").write_text("body {}")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    refresh.package(site, first)
    refresh.package(site, second)

    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    with zipfile.ZipFile(first) as bundle:
        assert bundle.namelist() == ["assets/style.css", "index.html"]


def test_active_refresh_lease_prevents_overlap(monkeypatch, tmp_path):
    configure_cache(monkeypatch, tmp_path)
    refresh.acquire("first")
    with pytest.raises(SystemExit, match="refresh already active: first"):
        refresh.acquire("second")
    refresh.release("first")


def test_stale_refresh_lease_is_replaced(monkeypatch, tmp_path):
    configure_cache(monkeypatch, tmp_path)
    refresh.write_json(
        refresh.LEASE,
        {"run_id": "stale", "created_at": (refresh.now() - dt.timedelta(hours=3)).isoformat()},
    )

    refresh.acquire("new")

    assert refresh.read_json(refresh.LEASE)["run_id"] == "new"
    assert list(refresh.CACHE.glob("lease.stale.*.json"))


def test_optimize_bundle_removes_maps_and_rewrites_duplicate_images(tmp_path):
    site = tmp_path / "site"
    first = site / "one" / "assets" / "mascot.png"
    second = site / "two" / "docs" / "mascot.png"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"same image")
    second.write_bytes(b"same image")
    (site / "one" / "index.html").write_text('<img src="assets/mascot.png">')
    (site / "two" / "index.html").write_text('<img src="docs/mascot.png">')
    source_map = site / "assets" / "app.js.map"
    source_map.parent.mkdir()
    source_map.write_text("debug")

    result = refresh.optimize_bundle(site)

    assert result == {"source_maps_removed": 1, "duplicate_images_removed": 1}
    assert first.exists()
    assert not second.exists()
    assert not source_map.exists()
    assert '../one/assets/mascot.png' in (site / "two" / "index.html").read_text()
