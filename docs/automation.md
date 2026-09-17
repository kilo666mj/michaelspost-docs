# Refresh automation and recovery

## Schedule and update latency

A fresh agent checks the site every 24 hours. It fast-forwards this repository,
resolves the 15 configured public source refs, and runs the complete importer,
renderer, link, accessibility, and contrast validation. Normal source changes
therefore appear in Rendercase within 24 hours plus build time.

The agent publishes only when the central site commit or at least one resolved
source commit changed. `site_built_at` is deliberately excluded from change
detection, so a no-op build does not create a new immutable artifact version or
make old documentation look newer.

## Serialized publication

`scripts.refresh` owns a local two-phase publication record below ignored
`.cache/refresh/`:

1. `prepare` acquires a lease, runs `make check`, scans the generated bundle for
   likely credentials, deduplicates identical images, converts PNGs larger than
   1 MB with `cwebp`, creates a deterministic ZIP, and compares the source
   fingerprint with the last successful publication.
2. The publishing agent uploads a changed candidate to the artifact identified
   by `rendercase.json`. It updates the existing private artifact and never
   creates a capability share.
3. `record` verifies the site checkout did not move, records the committed
   Rendercase version and manifest hash, and releases the lease.

An active lease prevents overlapping agents from publishing out of order. A
lease older than two hours is retained as a stale audit record and replaced by
the next run. Losing the ignored publication state is safe: the next run may
publish one redundant immutable version, then resumes normal change detection.

## Manual refresh

From a clean, current checkout:

```sh
run_id="manual-$(date -u +%Y%m%dT%H%M%SZ)"
uv run python -m scripts.refresh prepare --run-id "$run_id"
```

When the JSON result reports `changed: false`, no publication is needed. When
it reports `changed: true`, publish the returned archive as the next version of
the configured Rendercase artifact. After Rendercase returns the committed
version and manifest hash, record them:

```sh
uv run python -m scripts.refresh record \
  --run-id "$run_id" \
  --version VERSION \
  --manifest-sha256 MANIFEST_SHA256
```

Do not put upload tokens, session material, or Rendercase credentials in this
repository or the refresh state.

## Failure handling

If preparation or publication fails, record the bounded user-facing error and
release the lease:

```sh
uv run python -m scripts.refresh fail --run-id "$run_id" --message "summary"
```

One failure remains local for the next retry. Two consecutive failures are
persistent: the scheduled agent opens or updates a `docs-refresh-failure` issue
in this repository with the failing stage and safe error summary. A successful
publication clears the failure counter and the agent closes the tracking issue.

Recovery is intentionally conservative:

- fix source documentation in its owning repository;
- fix importer, catalog, theme, or rendering failures here;
- inspect `uv run python -m scripts.refresh status` before clearing a lease;
- use `fail` to release a known failed run rather than deleting state by hand;
- rerun `prepare`, then publish the returned exact archive without rebuilding it.
