# Agent instructions

This repository is the presentation and discovery layer for Michael's public
project documentation. Project-specific facts, procedures, examples, and API
reference remain authoritative in their source repositories.

Do not hand-edit imported documentation or commit generated site output. Change
project documentation in the owning repository, then rebuild this site.

Keep cross-project material, navigation, theme, catalog metadata, import logic,
and build validation here. A new public project must be added to `projects.yml`
and pass its schema and link checks.

Never publish private DNS names, internal zone names, private addresses,
credentials, deployment inventory, or other environment-specific identifiers.
Use RFC-reserved example domains and addresses in public examples.

Before completing a change, run the documented validation and production build
commands. Preserve source-repository and resolved-commit attribution on every
imported project page.

