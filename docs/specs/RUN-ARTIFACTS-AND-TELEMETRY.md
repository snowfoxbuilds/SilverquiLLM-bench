Status: SETTLED

Last updated: 2026-05-13

# Run Artifacts and Telemetry

The runner produces artifacts for evaluation, auditability, recovery, and observability. Evaluatable state comes from the Workspace. `/output/` and Docker logs are telemetry only.

## Context

Agent Containers run for long periods and may modify many files. The runner needs enough observability to monitor progress and enough recovery support to avoid losing a run when timeout cuts off or corrupts the final Workspace.

## Design

### Official evaluation Workspace

Every run materializes:

```plain text
results/{run_name}/workspace_final/
```

This is the official source for evaluation.

- If no fallback was used, `workspace_final/` is the final harvested Workspace.
- If snapshot fallback was used, `workspace_final/` is the selected whole-Workspace snapshot.
- `workspace_final/` contains the full Workspace tree, not a reduced subset.
### Snapshot repo

During container execution, the runner captures a Workspace snapshot every 60 seconds.

Snapshots are host-side Git commits:

```plain text
results/{run_name}/snapshots/
  .git/
  workspace/
    prompt.md
    run_manifest.json
    engine/
    cards/
    rulebook.md
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
2. If `tests/engine/` fails, errors on import, hangs, times out, or cannot start, walk snapshots backward.
3. Select the latest whole-Workspace snapshot whose `tests/engine/` completes and passes within the normal engine-test timeout.
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
results/{run_name}/snapshot_telemetry.jsonl
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
Card telemetry uses IDs only, not card names.

### Output Directory

`/output/` is observability only. It pipes agent and process output out of the container for live monitoring and debugging.

No files in `/output/` are required. The runner must tolerate it being empty.

Optional conventions:

```plain text
/output/
  progress.jsonl
  system.log
  agent_stdout.log
  agent_stderr.log
  exit_code
```

No evaluatable state should depend on `/output/`.

### Docker logs

Independently of optional `/output/` files, the runner captures Docker process stdout and stderr.

Save:

```plain text
results/{run_name}/docker_stdout.log
results/{run_name}/docker_stderr.log
```

Stream them live to the terminal while saving.

Live terminal output should be labeled and colorized by type:

```plain text
[runner]    runner/system messages
[snapshot]  snapshot telemetry
[stdout]    Docker stdout
[stderr]    Docker stderr
[error]     runner errors
```

Color behavior:

- `--color auto` by default: enabled for interactive TTY, disabled for pipes/CI.
- `--color always`
- `--color never`
Saved log files remain plain split-stream logs.

A separate post-run `logs --run` viewer is deferred for v1.

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
- three evaluation dimensions
- telemetry/log artifact paths
### Filtered runs

The `--cards` filter is for development, debugging, and Pipeline Validation Runs only.

Rules:

- It filters SOS targets only.
- FDN examples are staged in full.
- Evaluation runs only on staged SOS targets.
- `run_summary.json` records the filter.
- Leaderboards exclude filtered runs by default.
- Leaderboard-valid runs require `card_filter = null` and the full SOS Draft Set staged.
### Smoke runs

`silverquillm smoke` is container-validation only, not benchmark evaluation.

Rules:

- Use a tiny synthetic Workspace.
- Do not use real SOS cards.
- Do not enter leaderboard or benchmark summaries.
- Validate image boot, volume mounts, basic file writing, and auth/model reachability.
## Decisions

- **`workspace_final/`**** is canonical**: Evaluation reads from the full official evaluation Workspace.
- **Snapshots are full Workspace Git commits**: Snapshot every 60 seconds, host-side, outside the container.
- **Snapshot fallback is whole-Workspace**: Do not mix final card implementations with earlier engine snapshots.
- **Fallback viability uses Engine Regression only**: `tests/engine/` is the snapshot selection gate.
- **No viable snapshot means no viable output**: Mark the run `no_viable_output_produced` and skip SOS/FDN correctness.
- **Telemetry is filesystem-only**: Do not parse/import agent code for telemetry.
- **`/output/`**** is optional telemetry**: No required files; no scoring dependency.
- **Docker logs are captured by runner**: Stream live and save split stdout/stderr logs.
- **Filtered runs are not leaderboard-valid**: `--cards` is development/pipeline validation only.
- **Smoke runs are not benchmark runs**: Use synthetic Workspace and exclude from scoring.
