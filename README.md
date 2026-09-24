# michaelspost.com documentation

This repository builds a unified documentation catalog for Michael's public
projects without moving project documentation away from the repositories that
own the code. The public project index remains at `michaelspost.com/projects.html`;
this repository provides the catalog, importer, renderer, and validation source.

The site has three responsibilities:

1. Present the project catalog and explain how related projects fit together.
2. Import repository-owned README and `docs/` content for consistent navigation
   and search.
3. Record exactly which repository commit supplied every published page.

Project-specific documentation remains authoritative in its source repository.
The central site owns only cross-project explanations, catalog metadata, theme,
import logic, and published build metadata.

## Local development

The project supports Python 3.12 through 3.14 and uses MkDocs Material and
`uv` for reproducible dependencies:

```sh
make setup
make serve
```

The development server is available at `http://127.0.0.1:8000`. Catalog-backed
pages are generated into the ignored `build/` directory before MkDocs starts.
Restart `make serve` after changing `projects.yml` or generator code.

Build the production site into the ignored `dist/` directory and run all
validation with:

```sh
make build
make check
```

`make check` validates the catalog, generator tests, the strict MkDocs render,
internal links, basic HTML accessibility, and light/dark body-text contrast.

## Hosting status

The validated catalog is published at <https://docs.michaelspost.com/> as a
static nginx site on Spike behind the existing Cloudflare Tunnel. Deployment is
currently an explicit Ansible operation rather than a recurring job. Rendercase
artifact publication remains disabled; the retained artifact-refresh tooling is
dormant and does not participate in the public site.

## Status

The documentation build imports the configured README and `docs/` content from
all 15 public repositories. Every generated page records its source path,
immutable commit, source-update time, and edit link. The generated build
manifest records the complete source snapshot used for each build and any
future Rendercase version.

See:

- [Architecture and source policy](docs/architecture.md)
- [Authoring contract](docs/authoring.md)
- [Documentation validation and adoption](docs/validation.md)
- [Source-repository CI rollout](docs/ci-rollout.md)
- [Static-site deployment](docs/deployment.md)
- [Refresh automation and recovery](docs/automation.md)
- [Project catalog](projects.yml)
- [Catalog schema](projects.schema.json)
- [Contribution workflow](CONTRIBUTING.md)

## License

MIT
