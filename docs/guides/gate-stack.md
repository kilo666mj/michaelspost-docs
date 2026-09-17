# Gate stack

The five Gate projects split observation, local connection handling, shared
runtime code, and centralized policy. They are useful independently; adopting
one does not require deploying the whole stack.

## Responsibility map

| Project | Owns | Deliberately does not own |
| --- | --- | --- |
| [TLSGate](https://github.com/kilo666mj/tlsgate) | Passive TLS ClientHello fingerprinting, local decisions, connection limits, and TCP forwarding | TLS termination, backend authentication, or proof of client identity |
| [SSHGate](https://github.com/kilo666mj/sshgate) | Passive SSH KEXINIT fingerprinting, local decisions, connection limits, and forwarding to `sshd` | SSH user/key authentication or proof of device identity |
| [Gatekit](https://github.com/kilo666mj/gatekit) | Shared SQLite store, Gatehub client, rate limits, connection lifecycle, and graceful process handoff | Protocol parsing, a runnable service, or centralized policy |
| [Gatehub](https://github.com/kilo666mj/gatehub) | Administrator and node authentication, observation collection, decisions, audit history, and bounded correlation | Backend user authentication or inline traffic forwarding |
| [GateSignal](https://github.com/kilo666mj/gatesignal) | Access-log ingestion, privacy-limited scanner signals, aggregate analytics, and durable delivery | General log alerting, direct connection blocking, or gate policy |

## Data and decision flow

```text
TLS client ──> TLSGate ──> TLS backend
                  │
SSH client ──> SSHGate ──> sshd
                  │
          observations and policy
                  │
                  v
               Gatehub <── aggregate scanner signals ── GateSignal <── HTTP access logs
                  │
                  └── decisions return to the relevant TLSGate or SSHGate node

Gatekit is linked into TLSGate and SSHGate; it is not another network hop.
```

Every gate keeps a local SQLite decision store and can run without Gatehub.
Adding Gatehub centralizes review and synchronizes decisions, but it does not
turn spoofable fingerprints into credentials. GateSignal contributes aggregate
HTTP evidence to Gatehub; it never edits a gate database or applies a block
itself.

## Choose the smallest useful deployment

- Deploy **TLSGate alone** to reduce opportunistic TLS scanner noise in front
  of a service that retains its normal authentication and abuse controls.
- Deploy **SSHGate alone** for the same local review pattern ahead of `sshd`.
- Add **Gatehub** when several gate nodes need one review surface and shared
  decisions.
- Add **GateSignal** only when HTTP access logs can provide useful aggregate
  scanner evidence. Start it in shadow mode.
- Depend on **Gatekit** when developing a gate; operators do not deploy it as a
  separate service.

Do not deploy GateSignal merely to operate TLSGate or SSHGate, and do not expose
Gatehub's admin listener to nodes. Each component keeps a narrow interface so a
failure does not collapse every security boundary into one process.

## Safe adoption order

1. Deploy one protocol gate on a parallel high port with unknown clients
   allowed only for a bounded enrollment window.
2. Approve known fingerprints locally, disable enrollment, and confirm the
   backend still enforces its own authentication.
3. Register that node in Gatehub and verify observation upload plus policy pull
   before moving the production listener.
4. Repeat for other gate nodes.
5. Run GateSignal in shadow mode with a dedicated Redis namespace. Review its
   parsing, privacy, thresholds, and HA lease behavior.
6. Disable the former signal publisher before enabling GateSignal publish mode.
7. Keep Gatehub web enforcement disabled while reviewing candidates, then use
   an explicit canary list before broader enforcement.

Project-specific installation, configuration, and rollback steps stay in the
owning repositories. The order above describes integration boundaries and does
not replace their runbooks.

## Authentication boundaries

- A **gate fingerprint** is attacker-controlled metadata and never a login
  credential.
- A **Gatehub administrator** authenticates through OIDC on the separate admin
  surface.
- A **gate or signal node** authenticates to Gatehub with its registered bearer
  token or mTLS certificate identity and may act only as its own instance.
- A **backend user** authenticates to the real TLS service or `sshd`, regardless
  of the gate verdict.
- A **GateSignal output** uses a dedicated Gatehub or analytics credential;
  access logs never supply that authority.

Keep credentials and private topology in deployment configuration, not public
documentation. Protect every SQLite/Redis backup according to the credentials
and operational history it contains.

## Isolate failures

Start at the component nearest the failed boundary:

1. Confirm the backend is healthy without changing its authentication policy.
2. Check the local gate listener, database, limits, and verdict.
3. If local decisions work, inspect the gate's Gatehub upload and policy-pull
   logs, then verify the registered node identity.
4. For scanner correlation, check GateSignal input parsing, Redis, publisher
   ownership, and outbox depth before investigating Gatehub candidates.
5. Use Gatehub's enforcement-disabled mode to clear automated blocks without
   deleting manual decisions.

A Gatehub outage does not need to stop an otherwise healthy local gate. A gate
outage is not repaired by Gatehub, and a healthy GateSignal cannot compensate
for missing TLS sightings. Preserve local rollback paths for every inline gate.

## Authoritative project documentation

- [TLSGate README and runbooks](https://github.com/kilo666mj/tlsgate)
- [SSHGate README and runbooks](https://github.com/kilo666mj/sshgate)
- [Gatekit package documentation](https://pkg.go.dev/github.com/kilo666mj/gatekit)
- [Gatehub deployment, API, and operations](https://github.com/kilo666mj/gatehub)
- [GateSignal deployment, migration, and operations](https://github.com/kilo666mj/gatesignal)
