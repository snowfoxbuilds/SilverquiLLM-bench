Status: SETTLED

Last updated: 2026-05-24

# Run Artifacts and Telemetry

The runner produces artifacts for evaluation, auditability, recovery, and observability. Evaluatable state comes from the Workspace. `/output/` and Docker logs are telemetry only.

## Context

Agent Containers run for long periods and may modify many files. The runner needs enough observability to monitor progress and enough recovery support to avoid losing a run when timeout cuts off or corrupts the final Workspace.

## Design

### Official evaluation Workspace

Every run materializes:

```plain text
docker/<image-dir>/results/<run_name>/workspace_final/
```

This is the official source for evaluation.

- If no fallback was used, `workspace_final/` is the final harvested Workspace.
- If snapshot fallback was used, `workspace_final/` is the selected whole-Workspace snapshot.
- `workspace_final/` contains the full Workspace tree, not a reduced subset.
### Snapshot repo

During container execution, the runner captures a Workspace snapshot every 60 seconds.

Snapshots are host-side Git commits:

```plain text
docker/<image-dir>/results/<run_name>/snapshots/
  .git/
  workspace/
    prompt.md
    run_manifest.json
    engine/
    cards/
    rulebook.txt
    engine_api.md
    base_classes.py
    test_utils.md
```

Rules:

- Snapshot the full Workspace tree.
- Rely on Git deduplication for unchanged files.
- Skip empty commits if nothing changed.
- Still emit telemetry every 60 seconds.
- Do not mount `.git` into the container.
- Do not snapshot `/output/`.
### Snapshot fallback

Snapshot fallback recovers from final Workspace corruption, especially scrambled engine code after timeout or interruption.

Algorithm:

1. Try final harvested Workspace.
2. If `engine_tests/` fails, errors on import, hangs, times out, or cannot start, walk snapshots backward.
3. Select the latest whole-Workspace snapshot whose `engine_tests/` completes and passes within the normal engine-test timeout.
4. Materialize that selected snapshot as `workspace_final/`.
5. Evaluate all dimensions from `workspace_final/`.
Snapshot fallback is whole-Workspace fallback, not engine-only fallback. The runner must not combine final card implementations with an earlier engine snapshot.

If no snapshot is viable, mark the run:

```plain text
no_viable_output_produced
```

This is a run-level status only. SOS Card Correctness and FDN Card Regression are skipped because there is no coherent evaluatable Workspace. Preserve the broken final Workspace for debugging.

### Snapshot telemetry

After every 60-second snapshot interval, the runner writes telemetry to:

```plain text
docker/<image-dir>/results/<run_name>/snapshot_telemetry.jsonl
```

It also prints a human-readable console summary.

Telemetry is filesystem-only. It must not parse or import agent code.

Example event:

```json
{
  "ts": "2026-05-13T21:32:00Z",
  "elapsed_seconds": 3600,
  "snapshot_commit": "abc123",
  "changed_card_impls": ["042", "105"],
  "changed_card_tests": ["042"],
  "changed_engine_files": ["engine/casting.py"],
  "changed_engine_files_truncated": false,
  "changed_engine_files_count": 1,
  "completed_like_card_impls": ["001", "002", "042", "105"],
  "total_changed_card_impls": 14,
  "total_changed_card_tests": 3,
  "total_changed_engine_files": 6,
  "total_completed_like_card_impls": 14
}
```

Field meanings:

- `changed_card_impls`: card IDs whose `card_impl.py` changed since the previous snapshot.
- `changed_card_tests`: card IDs whose `tests.py` changed since the previous snapshot.
- `completed_like_card_impls`: card IDs whose `card_impl.py` differs from the original template.
- Engine path lists are capped, for example to 50 paths, with a truncation flag and full count.
In `snapshot_telemetry.jsonl`, card telemetry uses IDs only, not card names — this file is high-cadence and stays lean. Slow-cadence per-card artifacts (`status.json`, `result.json`) include `card_name` alongside `card_id` for human-readable triage. The live `[snapshot]` terminal channel resolves card names from `card_spec.json` at print time, so terminal output stays readable while the JSONL file stays lean.

Per-card `result.json` also carries `tests_hash` and `test_nodes` (grilling 2026-06-10). `CardResult` adds two additive fields: the SHA-256 of the audited `tests.py` bytes (empty string when absent) and one `test_node`/`outcome` row per executed test node, captured via an inline `conftest.py` (no `pytest-reportlog` dependency). These are pass/fail only by design — skipped/xfail nodes are not enumerated, so `test_nodes` may be shorter than `tests_total`. They power the harvest rows; legacy Validated Results lack the fields and get back-compat handling (fail rows derived from `errors`, null hash).

### Output Directory

`/output/` is observability only. It pipes agent and process output out of the container for live monitoring and debugging.

No files in `/output/` are required. The runner must tolerate it being empty.

Optional conventions:

```plain text
/output/
  system.log
  agent_stdout.log
  agent_stderr.log
  exit_code
```

No evaluatable state should depend on `/output/`.

JavaScript entrypoints populate these channels with a `log()` helper that writes to `/output/system.log`, tee agent output to `/output/agent_stdout.log`, and pass agent output through `process.stdout.write()` so Docker logs still capture it. Future bash entrypoints follow the same file-based channel separation.

### Docker logs

Independently of optional `/output/` files, the runner captures Docker process stdout and stderr.

Save:

```plain text
docker/<image-dir>/results/<run_name>/docker_stdout.log
docker/<image-dir>/results/<run_name>/docker_stderr.log
```

Stream them live to the terminal while saving.

Pipe-reader threads write `docker_stdout.log` and `docker_stderr.log` directly into `run_dir` in append mode. There is no `.tmp` intermediate and no post-run copy step; harvest reads the files in place.

Live terminal output is labeled, colorized by type, and mirrored to a per-channel append-only file under the run directory. The tabbed viewer (`silverquillm logs --run`) reads from these files in both live (tail) and archived (static) modes.

| Channel | Backing file | Source |
| --- | --- | --- |
| `[runner]` | `runner.log` | Runner-internal messages (stage, launch, harvest, evaluate) |
| `[snapshot]` | `snapshot_telemetry.jsonl` | 60-second Git snapshot telemetry (existing) |
| `[stdout]` | `docker_stdout.log` | Container stdout (existing) |
| `[stderr]` | `docker_stderr.log` | Container stderr (existing) |
| `[error]` | `runner_errors.log` | Runner-side errors and warnings |
| `[edit]` | `fast_telemetry.jsonl` | 1 Hz fast-tier edit detection (`card_impl.py` / engine mtimes) |
| `[system]` | `system.log` | Mirrored from `/output/system.log` to the host |

Per-channel files are append-only; no rotation or truncation during a run. The viewer is read-only — running it or not has zero effect on saved artifacts.

Color behavior:

- `--color auto` by default: enabled for interactive TTY, disabled for pipes/CI.
- `--color always`
- `--color never`
Saved log files remain plain split-stream logs.

v1 ships a `silverquillm logs --run` tabbed log viewer over the per-channel files above, lifted into v1 once the runner stabilized and a run surfaced concrete triage pain (grilling 2026-05-23). Live labeled streaming remains the default; the viewer is opt-in for both live (tail) and archived (static) inspection.

### Run summary

`run_summary.json` is the canonical machine-readable report. It should include:

- `run_status`
- `leaderboard_valid`
- `card_filter`
- `timeout_seconds`
- `deadline_utc`
- `docker_image`
- `used_snapshot_fallback`
- `snapshot_commit`
- `snapshot_utc`
- `fallback_scope`
- `fallback_reason`
- `workspace_final`
- `resumed_from` (Resume Leg only — `run_name` of the immediate prior leg)
- `resumed_image_changed` (Resume Leg only — true when `--image` differs from prior leg's `docker_image`)
- three evaluation dimensions
- telemetry/log artifact paths
Resume Legs (Benchmark Runs with `resumed_from` set) are linked into a Resume Chain via `resumed_from`. Chain traversal is by repeated lookup; the runner does not aggregate results across legs. The `silverquillm chain <run-id>` reader ships alongside `silverquillm resume` so `resumed_from` always has at least one consumer. Resume Legs are never leaderboard-valid: any run with `resumed_from` set has `leaderboard_valid = false`.

When a resume needs information about the prior run, the runner prefers artifacts written *during* the run (manifest at staging, snapshot ledger during execution) over artifacts written *at harvest* (`run_summary.json`). The manifest is the source of truth for input fields (image, timeout); the snapshot ledger is the source of truth for snapshot-fallback detection. `run_summary.json` is used only for fields it uniquely owns (notably `run_status`), and missing-summary handling is explicit per [BENCHMARK-RUNNER.md](BENCHMARK-RUNNER.md) → Resume.

### Filtered runs [SUPERSEDED — Grilling 2026-08-27]

Card-subset ("workload") runs are **retired**. A Benchmark Run always consumes
the benchmark's **entire** problem set in a single Workspace (HOB-BENCHMARKS.md).
Cheap pipeline validation / candidate calibration uses the dedicated **smoke
benchmark** (`benchmarks/smoke/`, below), not a filtered run. The `--cards` /
`card_filter` machinery survives only on the legacy entrypoint lineage until it
is retired (#66); no scored HOB run happens on that lineage (#39).

The superseded contract, retained only for the SOS (V1) legacy lineage:

- It filters SOS targets only.
- FDN examples are staged in full.
- Evaluation runs only on staged SOS targets.
- `run_summary.json` records the filter.
- Leaderboards exclude filtered runs by default.
- Leaderboard-valid runs require `card_filter = null` and every card in `config.json` `cards` staged (for v1, the 10 audited SOS cards).
### Smoke runs

Two distinct things share the word "smoke" — do not conflate them:

- **The `silverquillm smoke` command** — container-boot validation only, not
  benchmark evaluation. A tiny synthetic Workspace, no real cards; validates
  image boot, volume mounts, basic file writing, and auth/model reachability.
  Never enters leaderboard or benchmark summaries.
- **The smoke *benchmark*** (`benchmarks/smoke/`) — a real, tiny benchmark of
  already-validated FDN cards (known-good oracles + audited tests) for pipeline
  validation / candidate calibration. It runs like any other benchmark (whole
  problem set, one Workspace) but is never leaderboard-published
  (`leaderboard.eligible: false`). See HOB-BENCHMARKS.md → Run shape.

Rules for the `silverquillm smoke` command:

- Use a tiny synthetic Workspace.
- Do not use real SOS cards.
- Do not enter leaderboard or benchmark summaries.
- Validate image boot, volume mounts, basic file writing, and auth/model reachability.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-008](../adr/ADR-008-resume-legs-are-independent-benchmark-runs.md) | Resume Legs Are Independent Benchmark Runs |
| [ADR-009](../adr/ADR-009-resume-reads-prefer-run-time-artifacts-over-harvest-time-artifacts.md) | Resume Reads Prefer Run-Time Artifacts Over Harvest-Time Artifacts |
