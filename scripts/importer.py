"""Deterministically import repository-owned documentation into the site build."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import posixpath
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / ".cache" / "repositories"
IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
INLINE_LINK_RE = re.compile(
    r"(?P<prefix>!?\[[^\]]*\]\(\s*)(?P<angle><)?(?P<url>[^\s)>]+)(?(angle)>)(?P<suffix>[^)]*\))"
)
NESTED_IMAGE_LINK_RE = re.compile(
    r"(?P<prefix>\[!\[[^\]]*\]\([^)]+\)\]\(\s*)(?P<angle><)?(?P<url>[^\s)>]+)(?(angle)>)(?P<suffix>[^)]*\))"
)
REFERENCE_LINK_RE = re.compile(
    r"(?P<prefix>^\s*\[[^\]]+\]:\s*)(?P<angle><)?(?P<url>\S+?)(?(angle)>)(?P<suffix>\s*(?:['\"(].*)?$)",
    re.MULTILINE,
)
HTML_LINK_RE = re.compile(r"(?P<prefix>\b(?:href|src)=(?P<quote>['\"]))(?P<url>[^'\"]+)(?P=quote)")


class ImportFailure(RuntimeError):
    """A catalog source could not be imported safely and completely."""


@dataclass(frozen=True)
class ImportedPage:
    source_path: str
    output_path: str
    title: str
    source_updated: str


@dataclass(frozen=True)
class ImportedProject:
    project_id: str
    repository: str
    requested_ref: str
    resolved_commit: str
    pages: tuple[ImportedPage, ...]
    assets: tuple[str, ...]


def _run(args: list[str], *, cwd: Path | None = None, text: bool = True) -> str | bytes:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=text,
        )
    except FileNotFoundError as error:
        raise ImportFailure(f"required command is unavailable: {args[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or b"failed").strip()
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        raise ImportFailure(f"command failed ({' '.join(args[:4])}): {detail}") from error
    return result.stdout


def clean_repo_path(value: str) -> str:
    """Return a normalized repository-relative POSIX path or fail."""

    if not value or "\x00" in value or "\\" in value:
        raise ImportFailure(f"unsafe repository path: {value!r}")
    parts: list[str] = []
    for part in PurePosixPath(value).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ImportFailure(f"repository path escapes its root: {value}")
            parts.pop()
        else:
            parts.append(part)
    if not parts or value.startswith("/"):
        raise ImportFailure(f"unsafe repository path: {value!r}")
    return "/".join(parts)


class GitSnapshot:
    """A cached, bare, blob-filtered checkout resolved to one immutable commit."""

    def __init__(self, cache_root: Path, project_id: str, repository: str, ref: str):
        self.project_id = project_id
        self.repository = repository.rstrip("/")
        self.ref = ref
        self.git_dir = cache_root / f"{project_id}.git"
        self.commit = ""

    def sync(self) -> str:
        self.git_dir.parent.mkdir(parents=True, exist_ok=True)
        if not self.git_dir.exists():
            _run(["git", "init", "--bare", str(self.git_dir)])
            _run(["git", "--git-dir", str(self.git_dir), "remote", "add", "origin", self.repository])
            _run(["git", "--git-dir", str(self.git_dir), "config", "remote.origin.promisor", "true"])
            _run(
                [
                    "git",
                    "--git-dir",
                    str(self.git_dir),
                    "config",
                    "remote.origin.partialclonefilter",
                    "blob:none",
                ]
            )
        else:
            remote = str(
                _run(["git", "--git-dir", str(self.git_dir), "remote", "get-url", "origin"])
            ).strip()
            if remote.rstrip("/") != self.repository:
                raise ImportFailure(
                    f"{self.project_id}: cached origin {remote!r} does not match {self.repository!r}"
                )
        _run(
            [
                "git",
                "--git-dir",
                str(self.git_dir),
                "fetch",
                "--force",
                "--no-tags",
                "--filter=blob:none",
                "origin",
                self.ref,
            ]
        )
        self.commit = str(
            _run(["git", "--git-dir", str(self.git_dir), "rev-parse", "FETCH_HEAD^{commit}"])
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ImportFailure(f"{self.project_id}: resolved an invalid commit: {self.commit!r}")
        return self.commit

    def _object(self, path: str) -> str:
        return f"{self.commit}:{clean_repo_path(path)}"

    def object_type(self, path: str) -> str | None:
        result = subprocess.run(
            ["git", "--git-dir", str(self.git_dir), "cat-file", "-t", self._object(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def read_bytes(self, path: str) -> bytes:
        if self.object_type(path) != "blob":
            raise ImportFailure(f"{self.project_id}: configured source file is missing: {path}")
        return bytes(
            _run(["git", "--git-dir", str(self.git_dir), "show", self._object(path)], text=False)
        )

    def read_text(self, path: str) -> str:
        try:
            return self.read_bytes(path).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ImportFailure(f"{self.project_id}: {path} is not UTF-8 Markdown") from error

    def list_files(self, root: str) -> list[str]:
        root = clean_repo_path(root)
        if self.object_type(root) not in {"blob", "tree"}:
            raise ImportFailure(f"{self.project_id}: configured source root is missing: {root}")
        raw = bytes(
            _run(
                [
                    "git",
                    "--git-dir",
                    str(self.git_dir),
                    "ls-tree",
                    "-r",
                    "-z",
                    "--name-only",
                    self.commit,
                    "--",
                    root,
                ],
                text=False,
            )
        )
        return sorted(item.decode("utf-8") for item in raw.split(b"\0") if item)

    def updated_at(self, path: str) -> str:
        value = str(
            _run(
                [
                    "git",
                    "--git-dir",
                    str(self.git_dir),
                    "log",
                    "-1",
                    "--format=%cI",
                    self.commit,
                    "--",
                    clean_repo_path(path),
                ]
            )
        ).strip()
        if not value:
            raise ImportFailure(f"{self.project_id}: no commit history found for {path}")
        return value


def output_path_for(project: dict, source_path: str) -> str:
    base = project["docs_path"].strip("/")
    if source_path == project["source"]["readme"]:
        return f"{base}/index.md"
    return f"{base}/{source_path}"


def page_title(markdown: str, source_path: str) -> str:
    in_fence = False
    for line in markdown.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        match = HEADING_RE.match(line) if not in_fence else None
        if match and len(match.group(1)) == 1:
            return re.sub(r"\s+#+$", "", match.group(2)).strip()
    return PurePosixPath(source_path).stem.replace("-", " ").replace("_", " ").title()


def normalize_headings(markdown: str, title: str, *, remove_first_h1: bool) -> str:
    lines = markdown.splitlines()
    in_fence = False
    found_h1 = False
    output: list[str] = []
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            output.append(line)
            continue
        match = HEADING_RE.match(line) if not in_fence else None
        if match and len(match.group(1)) == 1:
            if not found_h1:
                found_h1 = True
                if remove_first_h1:
                    continue
            else:
                line = "## " + match.group(2)
        output.append(line)
    if not found_h1 and not remove_first_h1:
        output = [f"# {title}", "", *output]
    return "\n".join(output).strip() + "\n"


def _relative_output(source_output: str, target_output: str) -> str:
    return posixpath.relpath(target_output, start=posixpath.dirname(source_output))


def _github_url(repository: str, commit: str, path: str, object_type: str) -> str:
    mode = "tree" if object_type == "tree" else "blob"
    return f"{repository}/{mode}/{commit}/{quote(path, safe='/')}"


def _referenced_destinations(markdown: str) -> set[str]:
    destinations: set[str] = set()
    in_fence = False
    outside: list[str] = []

    def collect() -> None:
        block = "\n".join(outside)
        for pattern in (NESTED_IMAGE_LINK_RE, INLINE_LINK_RE, REFERENCE_LINK_RE, HTML_LINK_RE):
            destinations.update(match.group("url") for match in pattern.finditer(block))
        outside.clear()

    for line in markdown.splitlines():
        if FENCE_RE.match(line):
            if not in_fence:
                collect()
            in_fence = not in_fence
            continue
        if not in_fence:
            outside.append(line)
    collect()
    return destinations


def _local_target(source_path: str, destination: str) -> tuple[str, str, str] | None:
    if destination.startswith(("#", "/")):
        return None
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    joined = str(PurePosixPath(source_path).parent / unquote(parsed.path))
    return clean_repo_path(joined), parsed.query, parsed.fragment


def _validate_svg(project_id: str, path: str, data: bytes) -> None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ImportFailure(f"{project_id}: referenced SVG is malformed: {path}") from error
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() == "script":
            raise ImportFailure(f"{project_id}: referenced SVG contains a script: {path}")
        for name, value in element.attrib.items():
            local_name = name.rsplit("}", 1)[-1].lower()
            if local_name.startswith("on"):
                raise ImportFailure(f"{project_id}: referenced SVG contains an event handler: {path}")
            if local_name == "href" and urlsplit(value).scheme in {"data", "http", "https", "javascript"}:
                raise ImportFailure(f"{project_id}: referenced SVG contains an external payload: {path}")


def _rewrite_destination(
    destination: str,
    *,
    snapshot: GitSnapshot,
    source_path: str,
    source_output: str,
    page_outputs: dict[str, str],
    asset_outputs: dict[str, str],
) -> str:
    local = _local_target(source_path, destination)
    if local is None:
        return destination
    target, query, fragment = local
    if target in page_outputs:
        path = _relative_output(source_output, page_outputs[target])
    elif f"{target.rstrip('/')}/README.md" in page_outputs:
        path = _relative_output(source_output, page_outputs[f"{target.rstrip('/')}/README.md"])
    elif target in asset_outputs:
        path = _relative_output(source_output, asset_outputs[target])
    else:
        object_type = snapshot.object_type(target)
        if PurePosixPath(target).suffix.lower() in IMAGE_SUFFIXES and object_type != "blob":
            raise ImportFailure(
                f"{snapshot.project_id}: {source_path} references a missing image: {target}"
            )
        if object_type is None:
            raise ImportFailure(
                f"{snapshot.project_id}: {source_path} references a missing local target: {target}"
            )
        path = _github_url(snapshot.repository, snapshot.commit, target, object_type)
    return urlunsplit(("", "", path, query, fragment))


def rewrite_links(
    markdown: str,
    *,
    snapshot: GitSnapshot,
    source_path: str,
    source_output: str,
    page_outputs: dict[str, str],
    asset_outputs: dict[str, str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        rewritten = _rewrite_destination(
            match.group("url"),
            snapshot=snapshot,
            source_path=source_path,
            source_output=source_output,
            page_outputs=page_outputs,
            asset_outputs=asset_outputs,
        )
        angle = "<" if match.groupdict().get("angle") else ""
        close_angle = ">" if angle else ""
        if "quote" in match.groupdict():
            quote_char = match.group("quote")
            return f'{match.group("prefix")}{rewritten}{quote_char}'
        return f'{match.group("prefix")}{angle}{rewritten}{close_angle}{match.group("suffix")}'

    def rewrite_block(lines: list[str]) -> str:
        block = "\n".join(lines)
        block = NESTED_IMAGE_LINK_RE.sub(replace, block)
        block = INLINE_LINK_RE.sub(replace, block)
        block = REFERENCE_LINK_RE.sub(replace, block)
        return HTML_LINK_RE.sub(replace, block)

    output: list[str] = []
    outside: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if FENCE_RE.match(line):
            if not in_fence and outside:
                output.extend(rewrite_block(outside).splitlines())
                outside.clear()
            in_fence = not in_fence
            output.append(line)
            continue
        if in_fence:
            output.append(line)
        else:
            outside.append(line)
    if outside:
        output.extend(rewrite_block(outside).splitlines())
    return "\n".join(output).strip() + "\n"


def _source_note(project: dict, snapshot: GitSnapshot, page: ImportedPage) -> str:
    source_url = _github_url(project["repository"], snapshot.commit, page.source_path, "blob")
    commit_url = f'{project["repository"]}/commit/{snapshot.commit}'
    edit_url = f'{project["repository"]}/edit/{quote(project["source"]["ref"], safe="")}/{quote(page.source_path, safe="/")}'
    return f'''<div class="source-note">
Source: <a href="{html.escape(source_url)}">{html.escape(page.source_path)}</a><br>
Commit: <a href="{html.escape(commit_url)}"><code>{snapshot.commit}</code></a><br>
Source updated: <time datetime="{html.escape(page.source_updated)}">{html.escape(page.source_updated)}</time>
&nbsp;·&nbsp; <a href="{html.escape(edit_url)}">Edit this page</a>
</div>'''


def _landing_page(project: dict, snapshot: GitSnapshot, page: ImportedPage, markdown: str) -> str:
    links = [f'[GitHub repository]({project["repository"]}){{ .md-button .md-button--primary }}']
    if project.get("package_url"):
        links.append(f'[Package reference]({project["package_url"]}){{ .md-button }}')
    body = normalize_headings(markdown, page.title, remove_first_h1=True)
    return f'''<p class="docs-eyebrow">{html.escape(project["kind"])}</p>

# {html.escape(project["name"])}

<span class="project-status">{html.escape(project["status"])}</span>

<p class="docs-lede">{html.escape(project["summary"])}</p>

{' '.join(links)}

{_source_note(project, snapshot, page)}

{body}'''


def import_project(project: dict, destination: Path, cache_root: Path) -> ImportedProject:
    source = project["source"]
    snapshot = GitSnapshot(cache_root, project["id"], project["repository"], source["ref"])
    snapshot.sync()

    readme = clean_repo_path(source["readme"])
    markdown_paths = {readme}
    for root in source["roots"]:
        markdown_paths.update(path for path in snapshot.list_files(root) if path.lower().endswith(".md"))
    markdown_by_path = {path: snapshot.read_text(path) for path in markdown_paths}
    page_outputs = {path: output_path_for(project, path) for path in markdown_paths}

    asset_paths: set[str] = set()
    for source_path, markdown in markdown_by_path.items():
        for destination_url in _referenced_destinations(markdown):
            local = _local_target(source_path, destination_url)
            if local and PurePosixPath(local[0]).suffix.lower() in IMAGE_SUFFIXES:
                asset_paths.add(local[0])
    asset_outputs = {
        path: f'{project["docs_path"].strip("/")}/{path}' for path in sorted(asset_paths)
    }

    for asset_path, output_path in asset_outputs.items():
        if snapshot.object_type(asset_path) != "blob":
            raise ImportFailure(
                f"{project['id']}: documentation references a missing image: {asset_path}"
            )
        data = snapshot.read_bytes(asset_path)
        if PurePosixPath(asset_path).suffix.lower() == ".svg":
            _validate_svg(project["id"], asset_path, data)
        target = destination / output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    pages: list[ImportedPage] = []
    for source_path in sorted(markdown_paths, key=lambda item: (item != readme, item)):
        raw = markdown_by_path[source_path]
        page = ImportedPage(
            source_path=source_path,
            output_path=page_outputs[source_path],
            title=project["name"] if source_path == readme else page_title(raw, source_path),
            source_updated=snapshot.updated_at(source_path),
        )
        rewritten = rewrite_links(
            raw,
            snapshot=snapshot,
            source_path=source_path,
            source_output=page.output_path,
            page_outputs=page_outputs,
            asset_outputs=asset_outputs,
        )
        if source_path == readme:
            rendered = _landing_page(project, snapshot, page, rewritten)
        else:
            rendered = (
                _source_note(project, snapshot, page)
                + "\n\n"
                + normalize_headings(rewritten, page.title, remove_first_h1=False)
            )
        target = destination / page.output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
        pages.append(page)

    return ImportedProject(
        project_id=project["id"],
        repository=project["repository"],
        requested_ref=source["ref"],
        resolved_commit=snapshot.commit,
        pages=tuple(pages),
        assets=tuple(sorted(asset_paths)),
    )


def import_all(catalog: dict, destination: Path, cache_root: Path | None = None) -> dict:
    cache_root = cache_root or Path(os.environ.get("DOCS_REPOSITORY_CACHE", DEFAULT_CACHE))
    projects = [import_project(project, destination, cache_root) for project in catalog["projects"]]
    manifest = {
        "schema_version": 1,
        "catalog_version": catalog["version"],
        "site_built_at": dt.datetime.now(dt.UTC).isoformat(),
        "projects": [
            {
                "id": project.project_id,
                "repository": project.repository,
                "requested_ref": project.requested_ref,
                "resolved_commit": project.resolved_commit,
                "pages": [
                    {
                        "source_path": page.source_path,
                        "output_path": page.output_path,
                        "title": page.title,
                        "source_updated": page.source_updated,
                    }
                    for page in project.pages
                ],
                "assets": list(project.assets),
            }
            for project in projects
        ],
    }
    (destination / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
