# michaelspost.com documentation

This repository builds the documentation hub planned for
`docs.michaelspost.com`. It gives Michael's public projects a shared front door
without moving project documentation away from the repositories that own the
code.

The site has three responsibilities:

1. Present the project catalog and explain how related projects fit together.
2. Import repository-owned README and `docs/` content for consistent navigation
   and search.
3. Record exactly which repository commit supplied every published page.

Project-specific documentation remains authoritative in its source repository.
The central site owns only cross-project explanations, catalog metadata, theme,
import logic, and published build metadata.

## Local development

The project uses Python 3.12, MkDocs Material, and `uv` for reproducible
dependencies:

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

## Publishing

Validated builds are published as private, immutable Rendercase artifacts. The
artifact bundle contains only the generated `dist/` tree, with `index.html` at
its root. Publishing a new build creates a new version; it does not create a
public capability link.

## Status

The shared shell, documentation-first theme, and catalog pages are implemented.
The multi-repository importer is the next implementation stage; until then,
each placeholder project page links directly to its authoritative GitHub
repository.

See:

- [Architecture and source policy](docs/architecture.md)
- [Authoring contract](docs/authoring.md)
- [Project catalog](projects.yml)
- [Catalog schema](projects.schema.json)
- [Contribution workflow](CONTRIBUTING.md)

## License

MIT
