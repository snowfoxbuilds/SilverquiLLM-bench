# Batch queue

The file-backed queue the bench-side scheduler executes (#39 §5, #66;
`docs/specs/BENCHMARK-CANDIDATES.md`). The substrate learns nothing about it.

- **`<id>.toml`** — one Batch: desired state, authored and edited in your
  editor, never written by the scheduler. Scanned in name order. **Batch ids
  are permanent, one-shot identifiers**: the committed state file is the
  record of what ran under that id, so never reuse an id for an unrelated
  batch — write a new file.
- **`state/<id>.json`** — the scheduler's observed state for that Batch,
  **committed to git**: one entry per started run with its state, run id,
  the candidate identity resolved at run start, timestamps and a sanitized
  outcome. Portable by construction — no absolute path, home directory,
  pid, hostname, container name, environment value or traceback ever enters
  it: an absolute `candidate` reference is recorded only as the label
  `<external-candidate>/<basename>` (the recorded identity says what ran, and
  pending entries always resolve from the batch file), and every outcome is
  redacted — the exact values bound to the candidate's declared secret slots,
  whatever their shape, a declared slot assigned any non-empty value (no
  length or character-set rule; a quoted value whole, escaped quotes
  included), then every generic credential shape and host path.
  The scheduler writes it atomically after every transition and never runs
  git; **you commit the checkpoints** (after each run, or each completed
  batch — replacement safety reaches exactly as far as the latest committed
  checkpoint).
- **`runtime/<id>.json`** — host-local runtime metadata (gitignored), present
  only while a run of that Batch is active: the batch, index and run id of
  the running entry, the scheduler pid and hostname. It names no container. A
  replacement scheduler on the same host binds it to the committed running
  entry and reconciles that entry's container, `silverquillm-<run-id>`.
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
silverquillm scheduler [--once] [--poll-seconds 30] [--results-repo <clone>] \
    [--replay-without-state <id>]... [--acknowledge-cleanup <id>]...
silverquillm queue ls
silverquillm top [--interval 2]
```

Semantics the scheduler enforces: serial execution in name order, then file
order; `not_before` respected; the file re-read before every not-yet-started
run (edits to a running Batch affect only runs not yet started); candidate
identity resolved and recorded at run start; a failed run recorded and the
Batch continued. `queue ls` and `top` are read-only.

Every scheduler log line is redacted before it is printed, the same way the
state is: generic credential shapes and host paths always (blocked and
malformed warnings, acknowledgements, recovery, the serve line — which names
the queue as `<batches>`), and the exact values bound to the candidate's
declared secret slots once a run's candidate has resolved (`STARTED`,
`DONE`/`FAILED`, executor errors, interruptions). Run ids and worker types
are recorded verbatim in the state; in the log they are redacted by value
like any other text.

## Starting a batch: the replay warning

A batch file with **no committed state** is blocked — nothing from it runs.
The scheduler warns that starting it from entry 0 may replay runs already
completed elsewhere (a lost checkout, a state file not yet committed) and
incur model and runtime costs, and `queue ls` / `top` show the same block.
Either restore the committed `state/<id>.json`, or acknowledge the replay
for **that one batch**:

```bash
silverquillm scheduler --once --replay-without-state 2026-09-04-hob
```

This creates the empty `state/2026-09-04-hob.json` and starts the batch from
run zero; commit the state file together with the batch file. There is no
global acknowledgement, and the flag refuses a batch that does not exist or
already has state. Malformed or newer-version state blocks a batch the same
way — nothing is repaired or replayed silently.

## Abandoned runs: what a replacement scheduler does first

Before any new work, under the lock, the scheduler reconciles every run the
previous scheduler left `running`. It first binds every `runtime/<id>.json`
to the committed state — batch, index and run id must match the running
entry exactly — before it touches any container; a runtime file that is
unreadable, malformed or names another run stops the scheduler with nothing
inspected or removed, and the file is kept for you to look at (`docker ps`,
remove by hand, delete the file). Then:

- **Same host** (`runtime/<id>.json` names this host): the container
  `silverquillm-<run-id>` of the bound entry — never a name read from the
  file — is force-removed and confirmed gone, then the run is marked
  `failed`. If removal fails or cannot be confirmed, the scheduler stops with
  a diagnostic and executes nothing — one scheduler and one run container per
  queue, always. Fix the container by hand and start again.
- **Another host** (no local runtime metadata — the state was committed
  elsewhere — or a valid runtime file naming another host): the run cannot
  be reconciled here. The scheduler stops until you confirm the container is
  gone on the host that ran it:

  ```bash
  silverquillm scheduler --acknowledge-cleanup 2026-09-04-hob
  ```

  The acknowledgement is for a replacement host only. It is refused while
  this host holds valid runtime metadata for the run (start without the flag
  and the container is reconciled here), and it is refused — the runtime
  file kept — while that metadata is unreadable or does not bind to the run.

SIGINT / SIGTERM interrupt the run in flight the same way (container
removed, run marked `failed`, scheduler unwinds); SIGKILL leaves the
`running` entry and its runtime file for the next startup to reconcile.

## Restore on a replacement host

Check out the repo with the committed `state/` and start the scheduler: every
batch resumes at its recorded cursor. What ran between the last committed
checkpoint and the failure is not known to the new host — commit after each
run if that window matters.
