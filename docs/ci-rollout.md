# Source-repository documentation CI rollout

All 15 imported repositories run the source Markdown validator on pushes to and
pull requests targeting their public `main` branch. Each workflow checks out
this repository at the immutable commit
`ea937a72a1187cadbbb3e3c9a908ac975f300990`; validator updates require a reviewed
pin change in every consumer. The workflow and setup actions are also pinned to
full commit SHAs.

Each repository has a pull-request template that asks authors to update affected
user, operator, API, or adoption documentation, or explain why no change is
needed. The documentation job is additive: existing build, test, race, lint,
security, release, and dependency workflows remain authoritative.

## Coverage and exceptions

| Repository | Markdown | Compilable examples | Generated reference |
| --- | --- | --- | --- |
| gatehub | README and `docs/` | Existing Go CI compiles package tests; operational snippets require a configured app | None committed |
| gatekit | README | Existing minimum/current Go CI compiles package tests | None committed |
| gatesignal | README and `docs/` | Existing Go CI compiles packages; CLI snippets require fixture data | None committed |
| sshgate | README and `docs/` | Existing Go CI compiles packages; operator commands require a deployment | None committed |
| tlsgate | README and `docs/` | Existing Go CI compiles packages; operator commands require a deployment | None committed |
| switchboard | README and `docs/` | Existing Go and client CI compile maintained code examples | None committed |
| wayminder | README and `docs/` | Existing Go CI compiles packages; MCP examples require backing services | None committed |
| rendercase | README and `docs/` | Existing Go CI compiles packages; publishing examples require an authenticated service | None committed |
| parallaxd | README and `docs/` | Existing Go CI compiles packages; drills require a deployment | None committed |
| rilldns | README and `docs/` | Existing Go CI compiles packages; DNS examples require isolated authorities | None committed |
| tintwire | README and `docs/` | Existing Go, browser, and desktop CI compile maintained examples | None committed |
| mcpkit | README | `example_test.go` runs in minimum/current Go CI | None committed |
| oidcrp | README | `example_test.go` runs in minimum/current Go CI | None committed |
| pwa-kit | README | `example_test.go`, the minimal app, and browser/worker tests run in CI | None committed |
| tintwire-go | README | `example_test.go` runs in minimum/current Go CI | None committed |

No repository had committed reference documentation generated from source at
the rollout audit on 2026-09-17, so no consumer invokes `--generated-command`.
This is an explicit exception, not a disabled check. A repository that adds a
committed generated reference must add its deterministic generator and output
path to the documentation workflow in the same pull request.

Fenced shell, configuration, and deployment snippets are not extracted into a
generic execution harness. Many intentionally require an identity provider,
database, DNS authority, browser, or multi-host deployment; running them in a
shared CI environment would weaken their stated safety boundary. Their owning
repositories retain focused unit, integration, acceptance, and syntax checks.
