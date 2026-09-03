Status: ACCEPTED

Date: 2026-05-25

# ADR-009: Resume Reads Prefer Run-Time Artifacts Over Harvest-Time Artifacts

## Context

`silverquillm resume <prior-run-id>` must read several fields from the prior Benchmark Run at staging time — `workspace_final/` existence, `docker_image`, snapshot-fallback state (`snapshot_utc`), prior `--timeout` and wall-clock-used, and `run_status`. Those fields live in different artifacts written at different times. The naive pattern of always reading `run_summary.json` (the canonical post-run report) silently breaks under harvester failure: the workspace and snapshot ledger may be intact while the summary is missing or truncated — and resume is precisely the feature that must recover from partially-failed runs.

## Decision

Prior-run artifacts fall into three categories by *when* they are written:

1. **Staging-time**: `run_manifest.json` — written immediately before container launch; input fields (image, timeout, deadline). Either present and complete, or absent.
2. **Run-time**: the snapshot ledger (`snapshots/.git/` plus `snapshot_telemetry.jsonl`) — written every 60 seconds during execution. Survives container crashes, Hard Timeout enforcement, and harvester failure.
3. **Harvest-time**: `run_summary.json` — written after the container exits and evaluation completes; evaluation outcomes and aggregate metadata. May be partial or absent if the harvester or evaluator crashed.

For any field that exists in multiple artifact categories, **resume reads prefer staging-time and run-time artifacts over harvest-time artifacts**.

Specifically:

- **`docker_image`**: read order is `run_manifest.json` → resolved path's `<image-dir>` component → `run_summary.json`. All available sources are cross-checked; mismatch aborts.
- **`--timeout`**: read from `run_manifest.json`.
- **Snapshot fallback bool + ****`snapshot_utc`**: read from the snapshot ledger only. Do not read `run_summary.json.used_snapshot_fallback` or `run_summary.json.snapshot_utc` for this purpose.
- **`run_status`**: read from `run_summary.json` (no alternative source). Missing-summary handling is explicit and gated by `--force-missing-summary` (see [BENCHMARK-RUNNER.md](../specs/BENCHMARK-RUNNER.md) → Resume).
- **Wall-clock-used**: read from `run_summary.json` (no alternative source for v1; could derive from snapshot ledger timestamps in future).
This makes resume staging resilient to the harvester-failed-but-workspace-is-fine case. It also makes the snapshot ledger format a stability contract: changing the ledger schema is now a breaking change for resume, not just for snapshot fallback.

## Consequences

**Positive:**

- Resume Legs can be started from runs whose harvester partially failed, with explicit opt-in (`--force-missing-summary`) for the fields that genuinely cannot be recovered.
- The snapshot ledger gets a second consumer (resume staging, in addition to snapshot fallback selection), which improves the chance that schema changes are noticed early.
- Cross-checking across multiple sources (`run_manifest.json`, `<image-dir>`, `run_summary.json`) catches corrupted run directories at staging time instead of mid-run.
**Negative:**

- Snapshot ledger format is now load-bearing for resume. Changes to the ledger require updating both snapshot-fallback code and resume staging code.
- More code paths per field — `docker_image` resolution has three sources and a cross-check, instead of one read.
- Resume staging knows about lower-level artifacts (manifest, ledger) rather than reading only the high-level summary. Slight layering violation, but the reliability gain is worth it.
**Neutral:**

- `run_summary.json` retains its role as the canonical post-run report for downstream tools (leaderboard scoring, `silverquillm chain` reader). Only resume *staging* has the read-source preference; everything else reads the summary as before.
## Alternatives Considered

**Trust ****`run_summary.json`**** first.** Read all resume-time fields from `run_summary.json` as the canonical source. Rejected because harvester failure (OOM, crash, partial write) silently breaks resume — workspace and ledger may be intact but resume refuses to start because summary is missing. The whole point of resuming a partially-failed run is precisely that the run was partial.

**Single-source-of-truth migration: promote all fields to the snapshot ledger.** Write `docker_image`, `--timeout`, etc. into the snapshot ledger so resume reads a single artifact. Rejected because (a) it duplicates manifest content into the ledger for no operational gain (manifest is already reliable), (b) it bloats every snapshot event with static metadata, and (c) `run_status` is genuinely a harvest-time concept and cannot move earlier.

**Single-source-of-truth migration: promote all fields to ****`run_manifest.json`****.** Write evaluation outcomes back to the manifest at harvest time. Rejected because it conflates input and output state, breaking the manifest's "snapshot of intent before launch" semantics.

**Read only from ****`<image-dir>`**** component for ****`docker_image`****.** The resolved path already encodes the image directory. Rejected because the `<image-dir>` is derived from `--image` via string stripping (`silverquillm-` prefix, `:tag` suffix); the inverse mapping is not bijective for all possible `--image` values, and we'd lose the cross-check that catches corrupted run dirs.

**No cross-check; first available source wins.** Read `run_manifest.json.docker_image`, return it, done. Rejected because it doesn't catch the case where a run dir was reconstructed by hand or copied between machines and the path no longer matches the manifest — exactly the situations where audit-trail integrity matters most.
