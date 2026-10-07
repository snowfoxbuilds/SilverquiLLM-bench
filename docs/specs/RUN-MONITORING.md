Status: DRAFT

Last updated: 2026-10-07

# Run Monitoring

`silverquillm top` is a read-only terminal monitor over this host's live Benchmark Runs, the batch queue, the Login Pools, and the Results Repo's history.

## Context

The scheduler and `silverquillm run` print nothing while a run is in progress, and the previous `top` showed only batch counts.
An operator needs to see what is running, what it costs, how close each Login Profile is to its weekly subscription limit, what is queued, and how past runs went, without reading run directories by hand.
This page replaces the historical image-run artifact and telemetry spec; that layout is recoverable from git history, and [Benchmark Runner](BENCHMARK-RUNNER.md) keeps the legacy runner overview (grilling 2026-10-07).

## Design

### Command and scope

`silverquillm top` opens the monitor; `silverquillm queue ls` stays the scriptable one-shot queue listing (grilling 2026-10-07).
The monitor is a Textual application shipped as the optional `monitor` extra (`silverquillm[monitor]`), so grader and candidate environments never install it; without the extra, `top` prints a one-line install hint.
Without a terminal, `top` draws nothing and points to `queue ls`.

The monitor is read-only (grilling 2026-10-07).
It never writes a file, takes a lock that a runner or the scheduler takes, stops or recovers a run, edits a Batch, or fetches or pulls the Results Repo.
Stopping a run, recovering, and editing the queue stay CLI and file operations.

Live views cover this host only: its Docker daemon, its run directory, its batch queue, and its Login Pools (grilling 2026-10-07).
History comes from the local Results Repo clone as it stands; runs from other hosts appear once the clone is pulled and show their host label.

### Locations and host configuration

The monitor resolves the Results Repo, batch queue directory, run directory, and state root exactly as every Karn command does, through the host configuration described in [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md#operator-entrypoints-and-records).
The status pane names each resolved location and the source it came from (flag, environment, or configuration file).

The configuration file also carries the monitor's own settings (grilling 2026-10-07):

| Key | Default | Meaning |
| --- | --- | --- |
| `[usage_rates] codex` | `5` | Estimated Cost in USD that counts as 1% of a Codex Login Profile's weekly allowance |
| `[usage_rates] claude` | `25` | Estimated Cost in USD that counts as 1% of a Claude Login Profile's weekly allowance |
| `[monitor] theme` | the built-in theme | Theme name, see Look and feel |

A provider is named by its login plugin: `karn-codex-login` is `codex`, `karn-claude-login` is `claude`.

### What the monitor reads

| Source | Used for |
| --- | --- |
| Docker containers labelled `org.silverquillm.run` | Which runs are executing, container start time, and the run directory (the `/workspace` bind source) |
| `<run-dir>/run-input.json` | Benchmark, construct, Login Profile, budget, and host start time of a live run |
| `<run-dir>/candidate/constructs/<construct>/definition.json` | Candidate display of a live run |
| The kernel's lock table (`/proc/locks`) for `<run-dir>/.runner.lock` and each Login Profile's `runner.lock` | Whether a runner or recovery still owns a run, and whether a Login Profile is busy, without taking or creating any lock |
| `<run-dir>/run-record.json` and `<run-dir>/recovery-N/run-record.json` | Whether a run's record is retained, whether its workspace writers were confirmed stopped, and its linked recovery |
| `<run-dir>/observations.events.jsonl` | Live request rows, provisional Estimated Cost |
| `docker logs -f`, then `<run-dir>/host/stdout.log` and `stderr.log` | Activity, stderr and raw tabs; Claude subscription usage readings |
| `<run-dir>/snapshots.json`, workspace git history | Workspace tab |
| `batches/<id>.toml` and `batches/state/<id>.json` | Queued runs and Batch status |
| Login Pool directories under the state root | Enrolled Login Profiles, and each one's pending login journal with the run that owns it |
| A Login Profile's stored login (`secret.json`) | The values its login plugin redacts, so live lines can be redacted; nothing derived from it is shown |
| A live Codex rollout under a busy Login Profile's `plugin/work/sessions/` | Codex subscription usage readings, the `rate_limits` field only |
| Results Repo `results/` and `exclusions/` | History, Exclusions, past durations, recorded subscription usage readings, and whether a retained record is published |

The monitor reads Results Repo files directly and caches each record by modification time, never through `runs.jsonl` (grilling 2026-10-07).
A Login Profile's `plugin/work` directory sits beside its live credentials, so the monitor reads nothing there except the `rate_limits` field of Codex rollout lines.

### Run stages

The monitor follows every run on this host that has a run directory or a run container, and puts each in exactly one stage (grilling 2026-10-07).
A stage comes from these observations, never from a record's existence alone:

| Observation | Source |
| --- | --- |
| Owner | Whether a process holds the run's `.runner.lock`; the runner and `silverquillm recover` both hold it, so it is read from the kernel's lock table and never taken |
| Container | Whether `sq-run-<run-id>` is running, stopped, or absent |
| Retained record | The original `run-record.json`, and any linked recovery `recovery-N/run-record.json` whose `recovery_of` names the run and whose writers were confirmed stopped |
| Final record | A linked recovery, or an original whose `execution.workspace_stopped` is true; an original with `workspace_stopped: false` is an unconfirmed observation and never final |
| Publication | Whether each retained record exists in the Results Repo under its Candidate Hash and run id; unknown when no Results Repo is resolved |
| Pending login | Whether a Login Profile's pending login journal names the run |

The first matching row decides the stage:

| Stage | Rule | Shown as |
| --- | --- | --- |
| Unknown | The kernel's lock table cannot be read | `?` |
| Starting | An owner holds the run, no record is retained, its container has not started, and no `host/host-result.json` exists | ◌ |
| Running | An owner holds the run, no record is retained, and its container is running | ▶ |
| Grading | An owner holds the run, no record is retained, and its container has stopped or been removed | ⚖ |
| Recording | An owner holds the run and a record is retained: the runner or a recovery is publishing, settling its login, or reconciling an unconfirmed stop | ✎ |
| Finished | No owner, a final record exists, every retained record of the run is published (or no Results Repo is resolved), and no pending login journal names the run | not shown; the run belongs to history |
| Needs recover | No owner, and anything else | red, top of the running pane |

Ownership comes from the kernel's lock table, never from taking the lock: a probe that held the lock even briefly could make a starting recovery refuse the run.

A Needs recover row names every reason that applies, and whether the run's container is still running:

| Reason | Meaning | What `silverquillm recover` does |
| --- | --- | --- |
| No record | The runner died before retaining a record; a detached container may still be running with nothing to harvest it | Stops the workload on request, grades once, and publishes |
| Unconfirmed stop | The only record is an original with `workspace_stopped: false` and no linked recovery | Stops the workload, settles the login, grades once, and retains and publishes a linked recovery; the original stays unchanged |
| Unpublished | A retained record, original or linked recovery, is missing from the Results Repo, though its scores may be final | Publishes the same retained record under the same id, without grading again |
| Login settlement pending | A pending login journal still names the run, so its login harvest failed or was interrupted | Settles that login under the login lock, preserving the run's native sessions first |

A linked recovery that is retained, published, and settled makes the run Finished, so the original's unconfirmed record stops raising a warning while staying unchanged in history.
A run directory with no `run-input.json`, no retained record, and no owner never launched; recovery has nothing to settle, so the monitor ignores it.
A published, stopped record in the Results Repo with no local retained record also counts as final.
A run directory whose records cannot be read, or that has more than one linked recovery, is shown as Needs recover with the error, since `recover` would refuse it too.

These cases must hold:

| Case | Stage over time |
| --- | --- |
| A normal run | Starting, Running, Grading, Recording while its record is published, then Finished |
| The runner is killed while the workload runs | Needs recover (no record), with the container still running |
| A record retained with `workspace_stopped: false` | Needs recover (unconfirmed stop) until a linked recovery is retained and published, then Finished |
| A record retained but not yet published | Needs recover (unpublished), even with final scores, until `recover` or a scheduler pass publishes it |
| A failed login harvest after a published, stopped record | Needs recover (login settlement pending) until settlement succeeds, then Finished |
| A recovery in progress | Recording while it holds the run, then Finished, or Needs recover with whatever it left unfinished |

### Candidate display

A Benchmark Candidate is shown as `name · model · effort`: the Construct Definition's `name` and its `CONSTRUCT_MODEL` and `CONSTRUCT_EFFORT` runtime environment values, with `—` for a missing value (grilling 2026-10-07).
A Construct Definition's name alone does not identify a configuration, since one name has been built with different models and efforts, and every rebuild changes the Candidate Hash.
Secondary labels, shown dimmed, are the first eight characters of the Candidate Hash and the image's recipe revision.

### Dashboard

The dashboard has three panes: a narrow status pane across the top, the running pane filling most of the bottom left, and a narrow queued pane on the bottom right.
Live panes refresh every two seconds by default (`--interval`).

The status pane shows (grilling 2026-10-07):

- the resolved locations and their sources, and the Results Repo clone's last fetch time and how many commits it is behind its remote-tracking branch, both from local refs;
- counts of queued runs, live runs (every stage but Finished), and runs finished in the last seven days, with the all-time total dimmed;
- for each Login Pool, every Login Profile with a free or busy marker and its Estimated Weekly Usage.

Each running-pane row shows the stage, benchmark, Candidate display, Login Profile, elapsed container time, an elapsed-versus-budget bar, Estimated %, provisional Estimated Cost, and a cost sparkline.
Selecting a row opens its run details.

**Estimated %** is the elapsed container time divided by the median container duration (`stopped_at` minus `started_at`) of completed, non-excluded runs of the same benchmark (grilling 2026-10-07).
Those runs are the same Candidate Hash's when it has any, and otherwise the same Candidate display's.
The figure stays at most 99% while the run is live and is blank when no such run exists.

**Provisional Estimated Cost** comes from the run's live telemetry events (grilling 2026-10-07).
Codex request events are priced with the bench's price table, as at the end of a run.
Claude request events lack the cache-write duration split that the price table needs, so Claude runs sum Claude Code's own per-request `cost_usd`.
The figure is marked `~` until the Run Record exists, then shows the record's Estimated Cost; with native telemetry off it is blank.

The queued pane lists the not-yet-started run specs in execution order, under one header line per Batch (grilling 2026-10-07).
Each row shows the benchmark, Candidate display, and budget; a queued run has no Login Profile until it launches.
A Batch header shows a countdown to its `not_before`, or `⚠ needs ack` for a Batch with no committed state.

### Estimated Weekly Usage

Each Login Profile shows its Estimated Weekly Usage and how old the underlying observation is (grilling 2026-10-07).

A subscription usage reading is a provider's own report of the weekly window: a utilization percentage, a reset time, and when it was observed.
Claude reports one in its `rate_limit_event` stdout lines (the `seven_day` window); Codex reports one in its rollout `rate_limits`, as whichever of its windows lasts 10080 minutes (see [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md#efficiency-measurements)).
The monitor takes the newest reading for a Login Profile from its live run's output, else from the Run Records that name that Login Profile.

A reading speaks for its own weekly window, and for one window after that at most:

| Situation | Shown value |
| --- | --- |
| The newest reading's reset time has not passed | The reading's utilization, plus the Estimated Cost observed on the Login Profile after the reading divided by the provider's rate, marked `≈` when that addition is nonzero |
| The newest reading's reset time has passed, less than seven days ago | The Estimated Cost observed on the Login Profile since that reset, divided by the provider's rate, marked `≈` |
| The newest reading's reset time passed seven days ago or more, or no reading exists | The Estimated Cost observed on the Login Profile over the last seven days, divided by the provider's rate, marked `≈` |

A newer reading always replaces whatever an older one implied.
Only a value from an unexpired reading shows a reset time; after the reset, the provider's next reset is unknown, so none is shown.

Live runs count with their provisional Estimated Cost, and excluded runs count too, since an Exclusion does not undo spend.
A value from an unexpired reading reads like `41% · resets Thu 14:00 · read 12m ago`.

### Historic view

The historic view browses by benchmark, by Candidate display, or by run (grilling 2026-10-07).
Selecting a benchmark or a Candidate display lists its runs; a Candidate display expands to its individual Candidate Hashes.

A run occupies one line: run date, benchmark, Candidate display, execution status, container duration over budget, target-card pass rate with passed/total, FDN Card Regression pass rate, Engine Regression pass rate, Estimated Cost, Agent Turns, total tokens, Login Profile, host label, and the short run id.
Every column sorts.
Excluded runs are dimmed with their reason code, and a key hides them.
Combined Regression joins the line once records carry it.
Selecting a run opens its run details.

### Run details view

The header carries `● LIVE` or `◼ HISTORICAL`, the stage for a live run, the Candidate display and secondary labels, Login Profile, timings, scores, Estimated Cost with its breakdown, Agent Turns, and token usage, each as available (grilling 2026-10-07).

| Tab | Content |
| --- | --- |
| Activity | The candidate's stdout event stream rendered for reading: assistant text, tool calls with their commands, shortened tool results |
| Stderr | The candidate's stderr |
| Requests | One row per model request with model, token types, and cost, and a cost sparkline |
| Workspace | The agent's git commits and the snapshot timeline with files changed per snapshot |
| Raw | Unrendered stdout |

A live run's tabs follow `docker logs -f` and the events file; a historical run's tabs read the retained files.
Live Docker logs are unredacted, so the monitor applies the login plugin's redactions to every line before showing it.
Those redactions are the Login Profile's stored login when the follow starts, so a token the candidate refreshes mid-run is redacted only from the retained logs, which the host redacts with the refreshed values at capture.
A followed run keeps its newest 2000 lines, each cut at 16 KiB.
The native transcript is not shown: for Claude it largely duplicates stdout, and it sits beside the Login Profile's credentials.

### Navigation

Number keys and clicks on the view tabs switch between the dashboard, historic view, and run details; Enter or a click opens a row; Escape goes back; `q` quits.

### Look and feel

The monitor is a dense operations console with Magic: The Gathering flavour (grilling 2026-10-07): tapped and untapped glyphs for busy and free Login Profiles, a mana colour per provider, set-symbol-style benchmark badges, and sparklines.
Every colour, glyph, and border lives in one theme definition, so the look changes without touching the views.
The default theme reads on a 256-colour terminal, and `--no-flair` selects a monochrome, plain-glyph theme.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-012](../adr/ADR-012-independent-host-for-karn-benchmark-candidates.md) | Karn v4 execution and observations have an independent consumer contract |
| [ADR-014](../adr/ADR-014-silverquillm-runs-karn-constructs-without-ozolith.md) | The Karn commands, `top` among them, own the top level |
