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
    names = ", ".join(project["name"] for project in projects)
    return f'''<article class="family-card">
<span class="project-meta">{len(projects):02d} projects</span>
<h2><a href="{path}/">{html.escape(family["title"])}</a></h2>
<p>{html.escape(family["description"])}</p>
<small>{html.escape(names)}</small>
</article>'''


def project_card(project: dict, heading: str = "h2") -> str:
    return f'''<article class="project-card">
<span class="project-status">{html.escape(project["status"])}</span>
<{heading}><a href="{project['docs_path']}">{html.escape(project["name"])}</a></{heading}>
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
    return f'''<p class="terminal-kicker">Public project knowledge base</p>

# Find the project. Follow the system.

<p class="docs-lede">One searchable home for the architecture, adoption, deployment, and operation of Michael's {len(catalog["projects"])} public projects. Each project's repository remains the source of truth.</p>

[Browse all projects](#project-families){{ .md-button .md-button--primary }}
[How these docs work](about/architecture.md){{ .md-button }}

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
    cards = "\n".join(project_card(project) for project in projects)
    return f'''<p class="terminal-kicker">Project family</p>

# {family["title"]}

<p class="docs-lede">{html.escape(family["description"])}</p>

<div class="project-grid" markdown>
{cards}
</div>
'''


def project_page(project: dict, projects_by_id: dict[str, dict]) -> str:
    links = [f'[GitHub repository]({project["repository"]}){{ .md-button .md-button--primary }}']
    if project.get("package_url"):
        links.append(f'[Package reference]({project["package_url"]}){{ .md-button }}')
    related = "\n".join(
        f'- [{projects_by_id[item]["name"]}]({projects_by_id[item]["docs_path"]})'
        for item in project["related"]
    ) or "This project does not declare related projects yet."
    roots = ", ".join(f'`{root}/`' for root in project["source"]["roots"]) or "README only"
    return f'''<p class="terminal-kicker">{html.escape(project["kind"])}</p>

# {html.escape(project["name"])}

<span class="project-status">{html.escape(project["status"])}</span>

<p class="docs-lede">{html.escape(project["summary"])}</p>

{' '.join(links)}

!!! note "Documentation import is next"
    This catalog page is ready, but repository-owned documentation has not been imported yet. Until that pipeline lands, the linked GitHub repository is authoritative.

## Documentation sources

<div class="source-note">
Requested ref: <strong>{html.escape(project["source"]["ref"])}</strong><br>
Entry point: <strong>{html.escape(project["source"]["readme"])}</strong><br>
Additional roots: <strong>{roots}</strong>
</div>

## Related projects

{related}
'''


def generated_nav(catalog: dict) -> list[dict]:
    nav: list[dict] = [{"Home": "index.md"}]
    for family in sorted(catalog["families"], key=lambda item: item["order"]):
        projects = [p for p in catalog["projects"] if p["family"] == family["id"]]
        base = family_path(projects[0])
        pages: list[dict] = [{"Overview": f"{base}/index.md"}]
        pages.extend({project["name"]: project["docs_path"].strip("/") + "/index.md"} for project in projects)
        nav.append({family["title"]: pages})
    nav.append({"About": [{"Architecture": "about/architecture.md"}, {"Authoring": "about/authoring.md"}]})
    return nav


def generate() -> None:
    catalog = load_catalog()
    shutil.rmtree(BUILD, ignore_errors=True)
    GENERATED_DOCS.mkdir(parents=True)

    shutil.copytree(ROOT / "site_assets", GENERATED_DOCS / "assets")
    shutil.copytree(ROOT / "overrides", BUILD / "overrides")
    (GENERATED_DOCS / "about").mkdir()
    shutil.copy2(ROOT / "docs" / "architecture.md", GENERATED_DOCS / "about" / "architecture.md")
    shutil.copy2(ROOT / "docs" / "authoring.md", GENERATED_DOCS / "about" / "authoring.md")
    (GENERATED_DOCS / "index.md").write_text(homepage(catalog))

    projects_by_id = {project["id"]: project for project in catalog["projects"]}
    for family in catalog["families"]:
        projects = [p for p in catalog["projects"] if p["family"] == family["id"]]
        base = family_path(projects[0])
        family_dir = GENERATED_DOCS / base
        family_dir.mkdir(parents=True)
        (family_dir / "index.md").write_text(family_page(family, projects))
        for project in projects:
            target = GENERATED_DOCS / project["docs_path"].strip("/")
            target.mkdir(parents=True)
            (target / "index.md").write_text(project_page(project, projects_by_id))

    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text())
    config["nav"] = generated_nav(catalog)
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
