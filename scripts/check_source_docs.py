"""Validate repository-owned Markdown before the central site imports it."""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from scripts.importer import (
    FENCE_RE,
    HTML_LINK_RE,
    INLINE_LINK_RE,
    NESTED_IMAGE_LINK_RE,
    REFERENCE_LINK_RE,
)


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str


def markdown_files(root: Path) -> list[Path]:
    files = [root / "README.md"] if (root / "README.md").is_file() else []
    docs = root / "docs"
    if docs.is_dir():
        files.extend(sorted(docs.rglob("*.md")))
    return files


def outside_code(markdown: str) -> str:
    output: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            output.append(line)
    return "\n".join(output)


def destinations(markdown: str) -> list[str]:
    body = outside_code(markdown)
    found: list[str] = []
    for pattern in (NESTED_IMAGE_LINK_RE, INLINE_LINK_RE, REFERENCE_LINK_RE, HTML_LINK_RE):
        found.extend(match.group("url") for match in pattern.finditer(body))
    return found


def anchor_slug(value: str) -> str:
    explicit = re.search(r"\s*\{#([A-Za-z0-9_.:-]+)\}\s*$", value)
    if explicit:
        return explicit.group(1)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[`*_~]", "", value).strip().lower()
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return re.sub(r"[\s-]+", "-", value).strip("-")


def anchors(markdown: str) -> set[str]:
    found: set[str] = set()
    counts: dict[str, int] = {}
    for line in outside_code(markdown).splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        slug = anchor_slug(match.group(1))
        if not slug:
            continue
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        found.add(slug if count == 0 else f"{slug}_{count}")
    return found


def validate_repository(root: Path) -> list[Finding]:
    root = root.resolve()
    files = markdown_files(root)
    if not files:
        return [Finding(root, "README.md or docs Markdown is required")]
    anchor_cache = {path: anchors(path.read_text()) for path in files}
    findings: list[Finding] = []
    for page in files:
        for destination in destinations(page.read_text()):
            if destination.startswith("/"):
                continue
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc:
                continue
            target = page if not parsed.path else (page.parent / unquote(parsed.path)).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                findings.append(Finding(page, f"link escapes repository root: {destination}"))
                continue
            if target.is_dir():
                target = target / "README.md"
            if not target.exists():
                findings.append(Finding(page, f"missing local target: {destination}"))
                continue
            if parsed.fragment and target.suffix.lower() == ".md":
                available = anchor_cache.get(target)
                if available is None:
                    available = anchors(target.read_text())
                    anchor_cache[target] = available
                if unquote(parsed.fragment) not in available:
                    findings.append(Finding(page, f"missing Markdown anchor: {destination}"))
    return findings


def run_command(root: Path, command: str) -> None:
    args = shlex.split(command)
    if not args:
        raise SystemExit("generated-reference command cannot be empty")
    subprocess.run(args, cwd=root, check=True)


def check_generated_paths(root: Path, paths: list[str]) -> None:
    if not paths:
        raise SystemExit("--generated-command requires at least one --generated-path")
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *paths],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise SystemExit("generated documentation is stale:\n" + result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument(
        "--generated-command",
        action="append",
        default=[],
        help="command to regenerate committed reference output; may be repeated",
    )
    parser.add_argument(
        "--generated-path",
        action="append",
        default=[],
        help="generated file or directory that must remain clean; may be repeated",
    )
    parser.add_argument(
        "--go-test",
        action="store_true",
        help="run go test ./... so package examples and repository tests compile",
    )
    args = parser.parse_args()
    root = Path(args.repository).resolve()
    findings = validate_repository(root)
    if findings:
        raise SystemExit(
            "\n".join(f"{finding.path.relative_to(root)}: {finding.message}" for finding in findings)
        )
    for command in args.generated_command:
        run_command(root, command)
    if args.generated_command:
        check_generated_paths(root, args.generated_path)
    if args.go_test:
        if not (root / "go.mod").is_file():
            raise SystemExit("--go-test requires go.mod at the repository root")
        subprocess.run(["go", "test", "./..."], cwd=root, check=True)
    print(f"Validated {len(markdown_files(root))} Markdown files in {root}")


if __name__ == "__main__":
    main()
