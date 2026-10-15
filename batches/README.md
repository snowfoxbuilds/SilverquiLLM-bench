# Batch queue

The file-backed queue `silverquillm scheduler` executes, found through `--batches-dir` or `batches_dir` in the host configuration file.
Operator instructions live in [Karn benchmarking](../docs/KARN-BENCHMARKING.md).

- **`<id>.toml`** — one Batch, authored in your editor (or by a campaign top-up) and never written by the scheduler.
  Every `*.toml` file here is a submission: keep backups and drafts elsewhere.
  Batch ids are one-shot: the state file records what ran under that id, so write a new file instead of reusing one; a renamed file is a new Batch.
- **`state/<id>.json`** — the scheduler's observed state for that Batch (schema 2), written atomically after every transition.
- **`queue.json`** — the queue ledger: every Batch the scheduler has recorded here, in queue order, and whether it was acknowledged. Written only by the scheduler; never edit it.

All of these are host-local operational files, backed up with the host's raw data and never published.

## Batch file

```toml
format = "karn-v5"
not_before = 2026-10-01T09:00:00Z   # optional, timezone-aware, applies to the whole batch

[[runs]]
build_output = "/tmp/bench-codex-build"   # completed `karn build` output; relative paths resolve from the bench root
construct = "bare-codex"
benchmark = "hob-medium"
budget_seconds = 86400                     # optional, default 86400
native_telemetry = "auto"                  # optional: auto, codex, or none
```

`format`, `not_before`, and `runs` are the only top-level keys, and each run accepts only the keys above.
A run names no Login Profile: it takes any free one from its candidate's Login Pool when it starts.
The file is reread before every not-yet-started entry, so appending entries to a running batch is safe.

## Execution

- The scheduler fills free eligible Login Pool slots automatically, through the same lifecycle as `silverquillm run`; no concurrency setting is needed.
- Entries start in file order within a batch and can overlap. Batches with a slot available take priority in queue order, the order the scheduler first recorded them in `queue.json` (name order among those recorded together); a blocked batch does not hold up another batch's pool. Completion order can differ from start order.
- A running scheduler picks up a new batch file without a restart, and `queue ls` and `top` show it as pending. A batch is new when `queue.json` has never recorded it.
- A batch that `queue.json` records but whose state file is missing has lost its state. It is refused until you restore the state, or acknowledge a restart from entry 0 with `--replay-without-state <id>`, because that could replay finished runs. The same acknowledgement is needed once for each stateless batch present when a directory gets its first ledger, since nothing then tells a new batch from a lost one.
- `--replay-without-state <id>` acknowledges one start from entry 0. If that batch's state is lost again, even under the same scheduler, it needs a new acknowledgement, which means a scheduler restart.
- If `queue.json` is damaged, nothing is dispatched until it is repaired or removed; a removed ledger is rebuilt, and every batch without state then needs the acknowledgement. While it is damaged, `queue ls` and `top` show `ledger_damaged`, the scheduler warns on every pass, and `scheduler --once` exits non-zero.
- The batch directory itself must be writable: the scheduler writes `queue.json` there. If it cannot, dispatch stops the same way, with `queue_ledger_unwritable`.
- The scheduler warns, once per batch and in serve mode too, about every batch it skips and why.
- A failed entry is recorded with its evidence and the batch continues.
- An entry with no eligible slot stays pending, along with later entries in its batch. It counts as started only after claiming a slot.
- All runs left `running` by a crashed or killed scheduler are checked for recovery; runs still owned by a live worker are deferred. An unowned run that never wrote its run input is recorded as failed with `interrupted_before_launch`.
- A record that could not be written in time is marked `record_write_pending` and written on the scheduler's next start or by `silverquillm recover`.

The [Karn Benchmark Contract](../docs/specs/KARN-BENCHMARK-CONTRACT.md#operator-entrypoints-and-records) defines dispatch, recovery, and shutdown behavior, including the single concurrent run allowed for candidates without a login plugin.

`silverquillm queue ls` lists the queue without touching it; `silverquillm top` is the read-only monitor over the queue, live runs, Login Profiles and history (see `docs/specs/RUN-MONITORING.md`).

## Historical batches

Batch files declaring `format = "karn-v4"` predate `karn-v5` and still run unchanged; either format may name v4 or v5 builds.
Batch files with neither format, and schema 1 state files, belong to the removed Candidate Bundle scheduler.
They are shown as unsupported, logged once by the scheduler, and never run or rewritten.
