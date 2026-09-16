# Contributing

## Project documentation changes

Make project-specific changes in the repository that owns the code. Run that
repository's documented tests and documentation checks, then submit the code
and documentation together. The aggregate site will rebuild from the merged
source commit.

Do not patch imported build output in this repository. Such changes disappear
on the next refresh and leave the source README or `docs/` directory incorrect.

## Catalog and cross-project changes

Use this repository for:

- adding or retiring a public project in `projects.yml`;
- changing family membership or related-project links;
- explaining relationships that span repositories;
- changing imports, validation, navigation, search, or visual design;
- changing the static-site deployment.

For a new catalog entry:

1. Confirm the GitHub repository is public and authoritative.
2. Add all required metadata and content paths to `projects.yml`.
3. Use reserved example domains and addresses in all public documentation.
4. Run catalog validation, the importer, link checks, and the production build.
5. Confirm the rendered page identifies its source repository and commit.
6. Add the published documentation URL to the repository homepage metadata.

## Pull-request review

Reviewers should confirm:

- project-specific claims remain in the source repository;
- links and images work from both GitHub and the rendered site;
- examples are safe, reproducible, and free of private infrastructure details;
- generated reference has a source-repository drift check;
- the build manifest records immutable source commits;
- no generated site output or imported copies are committed.

