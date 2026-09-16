# Agent tooling stack

Switchboard, Wayminder, and Rendercase solve different parts of an agent
workflow. They can be used independently or combined without moving ownership
of data and security decisions into the gateway.

| Concern | Owning project | Boundary |
| --- | --- | --- |
| MCP discovery, identity-aware routing, policy, and approvals | [Switchboard](https://github.com/kilo666mj/switchboard) | Does not become the source of truth for an upstream service |
| Durable facts, decisions, preferences, procedures, and references | [Wayminder](https://github.com/kilo666mj/wayminder) | Not a secret manager, task tracker, transient log, or artifact store |
| Immutable interactive web bundles, viewing, and sharing | [Rendercase](https://github.com/kilo666mj/rendercase) | Not an agent-memory database or general document editor |

## Choose a connection shape

Connect a client directly when it needs only one service or when end-to-end
caller identity must remain visible to that service.

```text
agent client ── bearer credential ──> Wayminder or Rendercase
```

Use Switchboard when a client benefits from one MCP endpoint, centralized
profile selection, exact-tool policy, and approval handling across several
services.

```text
agent client ── OAuth ──> Switchboard ── service credential ──> upstream
                              │
                              ├── Wayminder
                              └── Rendercase
```

The gateway shape is not transparent identity propagation by default.
Wayminder records the dedicated gateway client as its authoritative agent.
Rendercase accepts a delegated user header only when the caller presents the
exact configured Switchboard service identity, and it resolves that subject to
an existing Rendercase user. Restrict gateway-to-upstream routes even when
application authentication is enabled.

## Typical workflow

1. Recall durable context from Wayminder before relying on an infrastructure or
   repository convention.
2. Use Switchboard to discover and call approved tools when several upstream
   services participate in the task.
3. Publish a self-contained interactive result to Rendercase when people need
   to inspect or share it.
4. Store the durable conclusion or artifact reference in Wayminder, not the
   artifact bundle or transient execution log.

Task state, source code, service data, and artifacts stay with their owning
systems. A Switchboard restart must not erase upstream state; a Wayminder
backup does not protect Rendercase artifacts; a Rendercase artifact is not a
substitute for source-controlled operational documentation.

## Authentication and authorization boundaries

- **Switchboard** authenticates its client, selects a profile, exposes an exact
  tool set, and applies its own approval policy before forwarding a call.
- **Wayminder** authenticates registered clients. All authenticated clients
  currently share the same memory visibility; scopes organize recall and are
  not ACLs.
- **Rendercase** owns artifact users, roles, visibility, shares, and audit
  records. Its browser origin and untrusted content origin must remain
  separate.

Use independent credentials for every direct client and for each gateway-to-
service connection. Keep tokens in the client environment or secret store,
never in public configuration examples. OAuth scopes and service identities
must match the audience expected by the receiving service.

## Isolate failures

Start at the boundary closest to the caller:

1. Confirm the client can initialize its configured MCP endpoint.
2. If using Switchboard, inspect profile selection, visible tools, policy, and
   the upstream session snapshot.
3. Check the owning service's health/readiness and authentication logs.
4. Test its database and storage dependencies.

A healthy Switchboard cannot make an unhealthy upstream ready. Conversely, a
healthy upstream can still be unavailable through Switchboard because the
profile, exact-tool policy, OAuth session, DNS, or outbound route is wrong.

The source repositories remain authoritative for current configuration and
recovery details:

- [Switchboard operator guide](https://github.com/kilo666mj/switchboard/blob/main/docs/operator-guide.md)
- [Switchboard troubleshooting](https://github.com/kilo666mj/switchboard/blob/main/docs/troubleshooting.md)
- [Wayminder documentation](https://github.com/kilo666mj/wayminder#documentation)
- [Rendercase operations](https://github.com/kilo666mj/rendercase/blob/main/docs/operations.md)
- [Rendercase troubleshooting](https://github.com/kilo666mj/rendercase/blob/main/docs/troubleshooting.md)
