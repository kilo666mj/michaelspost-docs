# Authoring contract

## Write documentation beside the code

A behavior change and its documentation should land in the same source-repo
pull request. Update documentation when a change affects commands,
configuration, APIs, deployment, security boundaries, upgrade behavior, or
observable user behavior.

The source repository README should remain useful without the central site. It
should state the project's purpose and boundary, show the shortest safe quick
start, and link to deeper material. Longer operational and reference material
belongs under `docs/`.

## Preferred structure

Use only the pages a project needs:

```text
README.md
docs/
  architecture.md
  configuration.md
  deployment.md
  operations.md
  security.md
  troubleshooting.md
examples/
```

Libraries may keep a focused README plus tested examples instead of creating a
large documentation tree. Applications should document how to deploy, operate,
upgrade, recover, and remove them safely.

## Links and assets

- Prefer repository-relative Markdown links for content within the same repo.
- Use root-relative links only for pages owned by this central site.
- Keep documentation images in the source repository, preferably below
  `docs/images/`.
- Give every image meaningful alternative text unless it is decorative.
- Link to source APIs and package references rather than copying generated
  output that cannot be checked for drift.
- Do not link to private services as prerequisites for a public quick start.

The importer rewrites repository-relative documentation links into site routes
when the target is imported. Other repository files link to the immutable
GitHub source view for the resolved commit. Missing local targets fail the
build.

## Generated reference

Configuration tables, CLI help, OpenAPI descriptions, MCP tool inventories, and
similar reference should be generated from code where practical. Generation
belongs to the source repository. Its CI must fail when regeneration changes
committed reference output.

Executable examples should be compiled or tested by the source repository.
The central site displays validated committed examples but does not execute
project code.

## Public examples and privacy

Never publish credentials, private DNS zones, real internal hostnames, private
addresses, inventory, account identifiers, or private topology. Use:

- `example.com`, `example.net`, and `example.org` for domains;
- `192.0.2.0/24`, `198.51.100.0/24`, and `203.0.113.0/24` for IPv4 examples;
- `2001:db8::/32` for IPv6 examples;
- clearly synthetic usernames, IDs, fingerprints, and tokens.

Security examples must preserve the project's real trust boundary. Do not make
an example shorter by disabling authentication, certificate verification,
authorization, or destructive-operation confirmation unless the example is an
explicitly labeled, loopback-only development mode.

## Reviews

Review project documentation for technical correctness in the source repo.
Review catalog, cross-project narrative, navigation, imports, and rendering in
this repository. Every imported page exposes an edit link that returns the
reader to the authoritative source file.

