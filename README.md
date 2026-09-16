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

## Status

The architecture and authoring contract are defined. Site scaffolding and the
multi-repository importer are the next implementation stages.

See:

- [Architecture and source policy](docs/architecture.md)
- [Authoring contract](docs/authoring.md)
- [Project catalog](projects.yml)
- [Catalog schema](projects.schema.json)
- [Contribution workflow](CONTRIBUTING.md)

## License

MIT

