# Documentation validation and adoption

The central repository provides two validation layers with different trust
boundaries:

- `make check-source` validates repository-owned Markdown where the code lives.
- `make check` resolves the catalog, imports exact public commits, builds the
  aggregate site, and validates the complete rendered surface.

The central importer never executes code from fetched repositories. Go tests
and generated-reference commands run only in the owning repository's CI.

## Source-repository checks

Use the validator against a repository checkout:

```sh
uv run python -m scripts.check_source_docs /path/to/project
```

It checks the root README and Markdown below `docs/` for local links, anchors,
referenced images, files, path escapes, and missing targets. External URLs are
left to the aggregate site's external-link policy.

For a Go repository, compile package examples and run its normal tests too:

```sh
uv run python -m scripts.check_source_docs /path/to/project --go-test
```

When reference files are generated from code, run the generator and require
the committed outputs to remain clean:

```sh
uv run python -m scripts.check_source_docs /path/to/project \
  --generated-command "go generate ./cmd/example" \
  --generated-path docs/reference.md
```

Commands are tokenized and executed directly without a shell. Repeat
`--generated-command` and `--generated-path` when a project has more than one
generator or output.

## Pinned adoption

Source repositories should run a pinned revision of this tooling. A CI job can
check out `kilo666mj/michaelspost-docs` at a full commit SHA into a temporary
directory, then invoke `scripts/check_source_docs.py` against the source
checkout. Do not track `main` from a required check: review and pin each tooling
upgrade like any other build dependency.

The rollout task adds this pattern to each public repository without replacing
its existing test, release, CodeQL, or dependency-update workflows. Go projects
should use `--go-test` only when the workflow does not already run the same
package tests.

The current repository-by-repository adoption and exception record is in the
[source-repository CI rollout](ci-rollout.md).

## Aggregate checks

`make check` validates `projects.yml` against `projects.schema.json`, resolves
every configured ref to an immutable commit, imports configured Markdown and
images, renders MkDocs in strict mode, and checks HTML landmarks, headings,
accessible link and image names, internal targets, and light/dark contrast.

The test suite includes valid, broken-link, broken-anchor, broken-image,
missing-content, path-traversal, link-rewrite, provenance, and manifest
fixtures. A failure blocks Rendercase publication.
