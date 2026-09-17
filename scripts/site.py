"""Generate, build, serve, and validate the documentation site."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from scripts.importer import import_all

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
GENERATED_DOCS = BUILD / "docs"
GENERATED_CONFIG = BUILD / "mkdocs.yml"


def load_catalog() -> dict:
    catalog = yaml.safe_load((ROOT / "projects.yml").read_text())
    schema = json.loads((ROOT / "projects.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(catalog)

    families = {family["id"] for family in catalog["families"]}
    projects = {project["id"] for project in catalog["projects"]}
    for project in catalog["projects"]:
        if project["family"] not in families:
            raise ValueError(f"{project['id']} references unknown family {project['family']}")
        unknown = set(project["related"]) - projects
        if unknown:
            raise ValueError(f"{project['id']} references unknown projects: {sorted(unknown)}")
    return catalog


def family_path(project: dict) -> str:
    return PurePosixPath(project["docs_path"].strip("/")).parts[0]


def family_card(family: dict, projects: list[dict]) -> str:
    path = family_path(projects[0])
    project_links = "\n".join(
        f'<li><a href="{project["docs_path"].strip("/")}/">{html.escape(project["name"])}</a></li>'
        for project in projects
    )
    return f'''<article class="family-card">
<span class="project-meta">{len(projects)} projects</span>
<h2><a href="{path}/">{html.escape(family["title"])}</a></h2>
<p>{html.escape(family["description"])}</p>
<ul class="project-list">
{project_links}
</ul>
</article>'''


def project_card(project: dict, href: str, heading: str = "h2") -> str:
    return f'''<article class="project-card">
<span class="project-status">{html.escape(project["status"])}</span>
<{heading}><a href="{href}">{html.escape(project["name"])}</a></{heading}>
<p>{html.escape(project["summary"])}</p>
<small class="project-meta">{html.escape(project["kind"])}</small>
</article>'''


def homepage(catalog: dict) -> str:
    projects_by_family = {
        family["id"]: [p for p in catalog["projects"] if p["family"] == family["id"]]
        for family in catalog["families"]
    }
    cards = "\n".join(
        family_card(family, projects_by_family[family["id"]])
        for family in sorted(catalog["families"], key=lambda item: item["order"])
    )
    return f'''<p class="docs-eyebrow">Project documentation</p>

# Build, deploy, and operate the stack

<p class="docs-lede">Practical documentation for Michael's {len(catalog["projects"])} public projects, organized by what you are trying to build or operate. Each project's repository remains the source of truth.</p>

<label class="docs-search" for="__search">
  <span class="docs-search__icon" aria-hidden="true">⌕</span>
  <span>Search all documentation</span>
  <kbd>/</kbd>
</label>

<nav class="docs-quick-links" aria-label="Documentation shortcuts">
  <a href="#project-families">Browse projects</a>
  <a href="guides/gate-stack/">Gate stack guide</a>
  <a href="guides/agent-tooling/">Agent tooling guide</a>
  <a href="about/architecture/">How these docs work</a>
</nav>

## Project families

<div class="family-grid" markdown>
{cards}
</div>

## Source-first documentation

Project documentation is written beside the code that it describes, then assembled here with source and commit attribution. Cross-project guides, navigation, search, and presentation live in this repository.

```text
source repositories  ->  validated import  ->  this searchable static site
```
'''


def family_page(family: dict, projects: list[dict]) -> str:
    cards = "\n".join(
        project_card(
            project,
            f'{project["slug"]}/',
        )
        for project in projects
    )
    return f'''<p class="docs-eyebrow">Project family</p>

# {family["title"]}

<p class="docs-lede">{html.escape(family["description"])}</p>

<div class="project-grid" markdown>
{cards}
</div>
'''


def generated_nav(catalog: dict, manifest: dict | None = None) -> list[dict]:
    imported = {project["id"]: project for project in (manifest or {}).get("projects", [])}
    nav: list[dict] = [{"Home": "index.md"}]
    for family in sorted(catalog["families"], key=lambda item: item["order"]):
        projects = [p for p in catalog["projects"] if p["family"] == family["id"]]
        base = family_path(projects[0])
        pages: list[dict] = [{"Overview": f"{base}/index.md"}]
        for project in projects:
            imported_pages = imported.get(project["id"], {}).get("pages", [])
            if len(imported_pages) <= 1:
                target = (
                    imported_pages[0]["output_path"]
                    if imported_pages
                    else project["docs_path"].strip("/") + "/index.md"
                )
                pages.append({project["name"]: target})
            else:
                project_pages = [{"Overview": imported_pages[0]["output_path"]}]
                project_pages.extend(
                    {page["title"]: page["output_path"]} for page in imported_pages[1:]
                )
                pages.append({project["name"]: project_pages})
        nav.append({family["title"]: pages})
    nav.append(
        {
            "Guides": [
                {"Gate stack": "guides/gate-stack.md"},
                {"Agent tooling stack": "guides/agent-tooling.md"},
            ]
        }
    )
    nav.append({"About": [{"Architecture": "about/architecture.md"}, {"Authoring": "about/authoring.md"}]})
    nav[-1]["About"].extend(
        [
            {"Documentation validation": "about/validation.md"},
            {"Refresh and recovery": "about/automation.md"},
        ]
    )
    return nav


def generate() -> None:
    catalog = load_catalog()
    shutil.rmtree(BUILD, ignore_errors=True)
    GENERATED_DOCS.mkdir(parents=True)

    shutil.copytree(ROOT / "site_assets", GENERATED_DOCS / "assets")
    (GENERATED_DOCS / "about").mkdir()
    (GENERATED_DOCS / "guides").mkdir()
    shutil.copy2(ROOT / "docs" / "architecture.md", GENERATED_DOCS / "about" / "architecture.md")
    shutil.copy2(ROOT / "docs" / "authoring.md", GENERATED_DOCS / "about" / "authoring.md")
    shutil.copy2(ROOT / "docs" / "validation.md", GENERATED_DOCS / "about" / "validation.md")
    shutil.copy2(ROOT / "docs" / "automation.md", GENERATED_DOCS / "about" / "automation.md")
    shutil.copy2(ROOT / "docs" / "guides" / "gate-stack.md", GENERATED_DOCS / "guides" / "gate-stack.md")
    shutil.copy2(ROOT / "docs" / "guides" / "agent-tooling.md", GENERATED_DOCS / "guides" / "agent-tooling.md")
    (GENERATED_DOCS / "index.md").write_text(homepage(catalog))

    manifest = import_all(catalog, GENERATED_DOCS)

    for family in catalog["families"]:
        projects = [p for p in catalog["projects"] if p["family"] == family["id"]]
        base = family_path(projects[0])
        family_dir = GENERATED_DOCS / base
        family_dir.mkdir(parents=True, exist_ok=True)
        (family_dir / "index.md").write_text(family_page(family, projects))

    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text())
    config["nav"] = generated_nav(catalog, manifest)
    GENERATED_CONFIG.write_text(yaml.safe_dump(config, sort_keys=False, width=100))
    print(f"Generated {len(catalog['projects'])} project pages across {len(catalog['families'])} families")


def run_mkdocs(command: str) -> None:
    subprocess.run(["mkdocs", command, "--config-file", str(GENERATED_CONFIG)], cwd=ROOT, check=True)


def build() -> None:
    generate()
    run_mkdocs("build")


def check() -> None:
    build()
    subprocess.run(["python", "scripts/check_site.py"], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "build", "serve", "check"))
    args = parser.parse_args()
    if args.command == "generate":
        generate()
    elif args.command == "build":
        build()
    elif args.command == "check":
        check()
    else:
        generate()
        run_mkdocs("serve")


if __name__ == "__main__":
    main()
