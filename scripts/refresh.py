"""Prepare and record serialized Rendercase documentation refreshes."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "refresh"
LEASE = CACHE / "lease.json"
CANDIDATE = CACHE / "candidate.json"
ARCHIVE = CACHE / "michaelspost-docs.zip"
PUBLISHED = CACHE / "published.json"
FAILURES = CACHE / "failures.json"
RENDERCASE_CONFIG = ROOT / "rendercase.json"
MAX_LEASE_AGE = dt.timedelta(hours=2)
SECRET_RE = re.compile(
    rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|Bearer [A-Za-z0-9_-]{20,}|"
    rb"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}"
)
HTML_ASSET_RE = re.compile(r'(?P<prefix>\b(?:href|src)=["\'])(?P<url>[^"\']+)(?P<suffix>["\'])')
IMAGE_SUFFIXES = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
LARGE_PNG_BYTES = 1_000_000


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def config() -> dict:
    value = json.loads(RENDERCASE_CONFIG.read_text())
    required = {"artifact_id", "entrypoint", "title", "visibility"}
    if set(value) != required or value["visibility"] != "private":
        raise SystemExit("rendercase.json must describe exactly one private artifact")
    return value


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def acquire(run_id: str) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    lease = read_json(LEASE)
    if lease:
        created = dt.datetime.fromisoformat(lease["created_at"])
        if now() - created <= MAX_LEASE_AGE:
            raise SystemExit(f"refresh already active: {lease['run_id']}")
        stale = CACHE / f"lease.stale.{created.strftime('%Y%m%dT%H%M%SZ')}.json"
        LEASE.replace(stale)
    try:
        descriptor = os.open(LEASE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise SystemExit("another refresh acquired the lease") from error
    with os.fdopen(descriptor, "w") as handle:
        json.dump({"run_id": run_id, "created_at": now().isoformat()}, handle)
        handle.write("\n")


def require_lease(run_id: str) -> dict:
    lease = read_json(LEASE)
    if not lease or lease.get("run_id") != run_id:
        raise SystemExit("refresh lease is missing or owned by another run")
    return lease


def release(run_id: str) -> None:
    require_lease(run_id)
    LEASE.unlink(missing_ok=True)
    CANDIDATE.unlink(missing_ok=True)


def source_state(manifest: dict, site_commit: str) -> dict:
    return {
        "site_commit": site_commit,
        "projects": {
            project["id"]: project["resolved_commit"] for project in manifest["projects"]
        },
    }


def digest(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def scan_bundle(directory: Path) -> None:
    for path in directory.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(directory)
        if relative.parts[:2] in {("assets", "javascripts"), ("assets", "stylesheets")}:
            continue
        if SECRET_RE.search(path.read_bytes()):
            raise SystemExit(f"possible secret in generated bundle: {relative}")


def rewrite_html_assets(directory: Path, replacements: dict[Path, Path]) -> None:
    for page in directory.rglob("*.html"):
        original = page.read_text()

        def replace(match: re.Match, page: Path = page) -> str:
            parsed = urlsplit(match.group("url"))
            if parsed.scheme or parsed.netloc or not parsed.path:
                return match.group(0)
            target = (page.parent / unquote(parsed.path)).resolve()
            replacement = replacements.get(target)
            if replacement is None:
                return match.group(0)
            relative = os.path.relpath(replacement, page.parent).replace(os.sep, "/")
            rewritten = urlunsplit(("", "", relative, parsed.query, parsed.fragment))
            return f'{match.group("prefix")}{rewritten}{match.group("suffix")}'

        updated = HTML_ASSET_RE.sub(replace, original)
        if updated != original:
            page.write_text(updated)


def webp_command(source: Path, destination: Path) -> list[str]:
    if converter := shutil.which("cwebp"):
        return [
            converter,
            "-quiet",
            "-resize",
            "768",
            "0",
            "-q",
            "82",
            str(source),
            "-o",
            str(destination),
        ]
    if converter := shutil.which("magick"):
        return [
            converter,
            str(source),
            "-resize",
            "768x>",
            "-quality",
            "82",
            "-define",
            "webp:method=6",
            str(destination),
        ]
    raise SystemExit("cwebp or ImageMagick is required to optimize large documentation images")


def optimize_bundle(directory: Path) -> dict[str, int]:
    """Remove development-only files and optimize imported image assets."""
    source_maps = list(directory.rglob("*.map"))
    for path in source_maps:
        path.unlink()

    groups: dict[tuple[str, str], list[Path]] = {}
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            key = (hashlib.sha256(path.read_bytes()).hexdigest(), path.suffix.lower())
            groups.setdefault(key, []).append(path)

    replacements: dict[Path, Path] = {}
    removed = 0
    for paths in groups.values():
        if len(paths) < 2:
            continue
        canonical, *duplicates = sorted(paths)
        replacements.update({path.resolve(): canonical.resolve() for path in paths})
        for duplicate in duplicates:
            duplicate.unlink()
            removed += 1
    rewrite_html_assets(directory, replacements)

    large_pngs = [path for path in directory.rglob("*.png") if path.stat().st_size >= LARGE_PNG_BYTES]
    converted = 0
    for source in large_pngs:
        destination = source.with_suffix(".webp")
        if destination.exists():
            raise SystemExit(f"image optimization target already exists: {destination}")
        subprocess.run(webp_command(source, destination), check=True)
        if destination.stat().st_size >= source.stat().st_size:
            destination.unlink()
            continue
        rewrite_html_assets(directory, {source.resolve(): destination.resolve()})
        source.unlink()
        converted += 1

    return {
        "source_maps_removed": len(source_maps),
        "duplicate_images_removed": removed,
        "large_pngs_converted": converted,
    }


def package(directory: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_suffix(".tmp.zip")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise SystemExit(f"bundle contains a symlink: {path.relative_to(directory)}")
            if not path.is_file():
                continue
            relative = path.relative_to(directory).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, path.read_bytes())
    temporary.replace(archive)


def prepare(run_id: str) -> None:
    acquire(run_id)
    if git("status", "--porcelain"):
        release(run_id)
        raise SystemExit("the documentation checkout is not clean")
    environment = os.environ.copy()
    environment.setdefault("UV_CACHE_DIR", str(ROOT / ".cache" / "uv"))
    subprocess.run(["make", "check"], cwd=ROOT, env=environment, check=True)
    manifest = json.loads((ROOT / "dist" / "build-manifest.json").read_text())
    site_commit = git("rev-parse", "HEAD")
    state = source_state(manifest, site_commit)
    previous = read_json(PUBLISHED)
    previous_state = previous.get("source_state") if previous else None
    if previous_state == state:
        FAILURES.unlink(missing_ok=True)
        release(run_id)
        print(json.dumps({"changed": False, "source_fingerprint": digest(state)}))
        return
    optimization = optimize_bundle(ROOT / "dist")
    subprocess.run([sys.executable, "-m", "scripts.check_site"], cwd=ROOT, check=True)
    scan_bundle(ROOT / "dist")
    package(ROOT / "dist", ARCHIVE)
    candidate = {
        "run_id": run_id,
        "created_at": now().isoformat(),
        "source_state": state,
        "source_fingerprint": digest(state),
        "bundle_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "optimization": optimization,
        "archive": str(ARCHIVE),
        "rendercase": config(),
    }
    write_json(CANDIDATE, candidate)
    print(json.dumps({"changed": True, **candidate}))


def record(run_id: str, version: int, manifest_sha256: str) -> None:
    require_lease(run_id)
    candidate = read_json(CANDIDATE)
    if not candidate or candidate.get("run_id") != run_id:
        raise SystemExit("candidate is missing or belongs to another run")
    if git("rev-parse", "HEAD") != candidate["source_state"]["site_commit"]:
        raise SystemExit("site source changed after the candidate was built")
    write_json(
        PUBLISHED,
        {
            "artifact_id": candidate["rendercase"]["artifact_id"],
            "version": version,
            "manifest_sha256": manifest_sha256,
            "published_at": now().isoformat(),
            "source_state": candidate["source_state"],
            "source_fingerprint": candidate["source_fingerprint"],
            "bundle_sha256": candidate["bundle_sha256"],
        },
    )
    FAILURES.unlink(missing_ok=True)
    release(run_id)
    print(json.dumps(read_json(PUBLISHED)))


def fail(run_id: str, message: str) -> None:
    require_lease(run_id)
    previous = read_json(FAILURES) or {"count": 0}
    value = {
        "count": int(previous.get("count", 0)) + 1,
        "last_failed_at": now().isoformat(),
        "message": message[:1000],
    }
    write_json(FAILURES, value)
    release(run_id)
    print(json.dumps(value))


def status() -> None:
    print(
        json.dumps(
            {
                "lease": read_json(LEASE),
                "candidate": read_json(CANDIDATE),
                "published": read_json(PUBLISHED),
                "failures": read_json(FAILURES),
                "rendercase": config(),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--run-id", required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--run-id", required=True)
    record_parser.add_argument("--version", required=True, type=int)
    record_parser.add_argument("--manifest-sha256", required=True)
    fail_parser = subparsers.add_parser("fail")
    fail_parser.add_argument("--run-id", required=True)
    fail_parser.add_argument("--message", required=True)
    subparsers.add_parser("status")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.run_id)
    elif args.command == "record":
        record(args.run_id, args.version, args.manifest_sha256)
    elif args.command == "fail":
        fail(args.run_id, args.message)
    else:
        status()


if __name__ == "__main__":
    main()
