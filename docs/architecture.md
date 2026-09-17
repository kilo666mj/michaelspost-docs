# Documentation architecture

## Decision

The generated documentation catalog is a static aggregation and presentation
layer. It does not become a second source of truth for any project. Automated
hosting is currently paused; the repository remains the build and validation
source.

The public information architecture is deliberately split across three
surfaces:

- `michaelspost.com` explains why projects exist through field notes and the
  portfolio page.
- The generated catalog provides discovery, cross-project explanations,
  consistent navigation, search, and rendered repository documentation when
  built locally or intentionally hosted.
- GitHub owns source, issues, releases, contribution history, and the canonical
  project documentation files.

## Ownership boundary

Source repositories own:

- project purpose and security boundaries;
- installation and quick-start instructions;
- configuration and API reference;
- deployment, operations, upgrades, and troubleshooting;
- examples that must remain compatible with the code;
- release-specific behavior.

This repository owns:

- the project catalog and family taxonomy;
- cross-project architecture and adoption guides;
- navigation, search, visual design, and accessibility;
- import and validation tooling;
- source-commit and build provenance;
- deployment of the static site.

Imported files are build artifacts. Corrections must be made in the source
repository and then re-imported.

## Project families

The catalog uses four stable families:

1. **Gate stack** — Gatehub, Gatekit, GateSignal, SSHGate, and TLSGate.
2. **Agent tooling** — Switchboard, Wayminder, and Rendercase.
3. **Infrastructure applications** — Parallaxd, RillDNS, and Tintwire.
4. **Shared libraries** — MCPKit, OIDCRP, PWA Kit, and Tintwire Go.

A project belongs to one primary family for navigation even when it integrates
with projects in another family. Cross-family relationships belong in catalog
metadata and cross-project guides, not duplicate pages.

## Page taxonomy

Each project landing page presents the available subset of this taxonomy:

1. Overview and status
2. Quick start
3. Concepts and architecture
4. Security and privacy boundary
5. Configuration or API reference
6. Deployment
7. Operations, upgrades, and troubleshooting
8. Examples and integrations
9. Source, releases, packages, and related projects

Applications normally need deployment and operations material. Libraries
normally need installation, ownership boundaries, compatibility, API links,
and executable examples. Empty placeholder pages are not published merely to
make every project look identical.

## Build technology

The site will use MkDocs Material with a small Python importer and validator.
The result is a static directory with no runtime database, authentication, or
secrets. Styling adapts michaelspost.com's Terminal Noir design without sharing
runtime code with the blog.

The importer reads `projects.yml`, resolves each configured repository ref to
an immutable commit, checks out that commit, and stages selected Markdown and
referenced assets into an ignored build directory. The renderer never edits the
source checkout.

## Source and version policy

The initial public site tracks each project's configured default branch,
currently `main`. Every build records both the requested ref and resolved commit
SHA. Pages show the source repository, source path, resolved commit, and an edit
link.

Two timestamps have distinct meanings:

- **Source updated** is derived from the latest Git commit affecting the source
  file.
- **Site built** records when the aggregate site was rendered.

Neither timestamp is entered manually. A new build that changes no source
commit must not make documentation appear newer.

Versioned documentation is deferred until a project supports multiple releases
that users still operate. At that point the catalog may select the latest stable
tag for the default view and expose `next` from `main`. The immutable source
commit remains the actual provenance in both cases.

## Refresh policy

The central workflow periodically compares resolved repository heads with the
last successful build manifest. It skips publication when neither sources nor
site code changed. Manual builds remain available for recovery.

Source repositories validate documentation in their own pull requests. The
central build validates imports, internal navigation, external links, and the
complete static render. Publication occurs only after all required checks pass.

## Failure and trust boundaries

Repository content is treated as build input, not executable instructions.
The importer accepts only configured public repositories and paths, rejects
path traversal and unsupported file types, and never executes repository code.
Generated reference material must be produced and validated by its owning
repository before it is imported.

The build uses no production credentials. Deployment credentials, DNS values,
and infrastructure inventory remain outside the public repository.
