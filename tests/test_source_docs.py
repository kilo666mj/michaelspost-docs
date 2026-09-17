from pathlib import Path

from scripts.check_source_docs import validate_repository

FIXTURES = Path(__file__).parent / "fixtures" / "source-docs"


def messages(name: str) -> list[str]:
    return [finding.message for finding in validate_repository(FIXTURES / name)]


def test_valid_source_documentation_passes():
    assert messages("valid") == []


def test_missing_link_is_reported():
    assert messages("broken-link") == ["missing local target: docs/missing.md"]


def test_missing_anchor_is_reported():
    assert messages("broken-anchor") == ["missing Markdown anchor: docs/guide.md#missing-section"]


def test_missing_image_is_reported():
    assert messages("broken-image") == ["missing local target: docs/images/missing.png"]
