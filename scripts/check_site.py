"""Small dependency-light checks for the generated HTML surface."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def contrast(first: str, second: str) -> float:
    def luminance(value: str) -> float:
        channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def target_for(page: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc or href.startswith(("mailto:", "tel:", "#")):
        return None
    raw = unquote(parsed.path)
    if not raw:
        return None
    if raw.startswith("/"):
        candidate = DIST / raw.lstrip("/")
    else:
        candidate = page.parent / raw
    if candidate.suffix:
        return candidate
    return candidate / "index.html"


def main() -> None:
    pages = sorted(DIST.rglob("*.html"))
    assert pages, "the build produced no HTML pages"
    failures: list[str] = []
    for page in pages:
        soup = BeautifulSoup(page.read_text(), "html.parser")
        label = page.relative_to(DIST)
        if not soup.html or soup.html.get("lang") != "en":
            failures.append(f"{label}: missing html[lang=en]")
        if not soup.main:
            failures.append(f"{label}: missing main landmark")
        if len(soup.select("main h1")) != 1:
            failures.append(f"{label}: expected exactly one main h1")
        for image in soup.find_all("img"):
            if image.get("alt") is None:
                failures.append(f"{label}: image missing alt text")
        for link in soup.select("main a[href]"):
            is_code_anchor = (link.get("id") or "").startswith("__codelineno-")
            if not is_code_anchor and not link.get_text(" ", strip=True) and not link.get("aria-label"):
                failures.append(f"{label}: link has no accessible name")
            target = target_for(page, link["href"])
            if target is not None and not target.exists():
                failures.append(f"{label}: broken internal link {link['href']}")

    palettes = {
        "terminal-noir": ("#d9e5df", "#0b100e"),
        "terminal-paper": ("#1d2420", "#f6f3ec"),
    }
    for name, (foreground, background) in palettes.items():
        ratio = contrast(foreground, background)
        if ratio < 7:
            failures.append(f"{name}: body contrast {ratio:.2f}:1 is below AAA")

    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Checked {len(pages)} pages: landmarks, headings, alt text, link names, links, and palette contrast")


if __name__ == "__main__":
    main()
