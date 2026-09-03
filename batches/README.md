# Batch queue

The file-backed queue the bench-side scheduler executes (#39 §5, #66;
`docs/specs/BENCHMARK-CANDIDATES.md`). The substrate learns nothing about it.

- **`<id>.toml`** — one Batch: desired state, authored and edited in your
  editor, never written by the scheduler. Scanned in name order.
- **`state/<id>.json`** — the scheduler's observed state for that Batch
  (gitignored): one entry per started run with its state, run id, and the
  candidate identity resolved at run start.
- **`.scheduler.lock`** — held with `flock` by the one running scheduler
  (gitignored); a second instance refuses to start.

## Batch file

```toml
not_before = 2026-09-04T02:00:00Z      # optional; RFC 3339 with an offset

[[runs]]
candidate = "candidates/vanilla-claude--4e8b75b6"   # a path, or a candidates/ entry name
mode = "basic"                                      # basic | planned
benchmark = "smoke"                                 # benchmarks/<id>/
budget_seconds = 14400

[[runs]]
candidate = "vanilla-codex--90a33424"
mode = "planned"
benchmark = "smoke"
budget_seconds = 14400
```

Exactly these keys. An unknown key, a `not_before` without an offset, or a
non-positive budget makes the file malformed: the scheduler skips it loudly
and `silverquillm queue ls` shows why.

## Commands

```bash
silverquillm scheduler [--once] [--poll-seconds 30] [--results-repo <clone>]
silverquillm queue ls
silverquillm top [--interval 2]
```

Semantics the scheduler enforces: serial execution in name order, then file
order; `not_before` respected; the file re-read before every not-yet-started
run (edits to a running Batch affect only runs not yet started); candidate
identity resolved and recorded at run start; a failed run recorded and the
Batch continued. `queue ls` and `top` are read-only.
