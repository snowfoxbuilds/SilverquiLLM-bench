# Batch queue

The file-backed queue `silverquillm scheduler` executes, found through `--batches-dir` or `batches_dir` in the host configuration file.
Operator instructions live in [Karn benchmarking](../docs/KARN-BENCHMARKING.md).

- **`<id>.toml`** — one Batch, authored in your editor and never written by the scheduler.
  Batches are scanned in name order.
  Batch ids are one-shot: the state file records what ran under that id, so write a new file instead of reusing one.
- **`state/<id>.json`** — the scheduler's observed state for that Batch (schema 2), written atomically after every transition.
  Commit it as runs finish; the scheduler never runs git.

## Batch file

```toml
format = "karn-v5"
not_before = 2026-10-01T09:00:00Z   # optional, timezone-aware, applies to the whole batch

[[runs]]
build_output = "/tmp/bench-codex-build"   # completed `karn build` output; relative paths resolve from --bench-root
construct = "bare-codex"
benchmark = "hob-medium"
budget_seconds = 86400                     # optional, default 86400
native_telemetry = "auto"                  # optional: auto, codex, or none
```

`format`, `not_before`, and `runs` are the only top-level keys, and each run accepts only the keys above.
A run names no Login Profile: it takes any free one from its candidate's Login Pool when it starts.
The file is reread before every not-yet-started entry, so appending entries to a running batch is safe.

## Execution

- Entries run serially in file order, through the same lifecycle as `silverquillm run`.
- A batch without committed state is blocked until acknowledged once with `--replay-without-state <id>`, because starting from entry 0 could replay finished runs.
- A failed entry is recorded with its evidence and the batch continues.
- An entry whose login another runner holds stays pending and is retried on the next pass.
- A run left `running` by a crashed or killed scheduler is recovered before anything else runs; one that never wrote its run input is recorded as failed with `interrupted_before_launch`.
- A record that could not be written in time is marked `record_write_pending` and written on the scheduler's next start or by `silverquillm recover`.

`silverquillm queue ls` lists the queue without touching it; `silverquillm top` is the read-only monitor over the queue, live runs, Login Profiles and history (see `docs/specs/RUN-MONITORING.md`).

## Historical batches

Batch files declaring `format = "karn-v4"` predate `karn-v5` and still run unchanged; either format may name v4 or v5 builds.
Batch files with neither format, and schema 1 state files, belong to the removed Candidate Bundle scheduler.
They are shown as unsupported, logged once by the scheduler, and never run or rewritten.
