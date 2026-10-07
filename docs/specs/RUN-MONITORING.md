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
| The kernel's lock table (`/proc/locks`) for `<run-dir>/.runner.lock` and each Login Profile's `runner.lock` | Whether a runner still owns a run, and whether a Login Profile is busy, without taking or creating any lock |
| `<run-dir>/observations.events.jsonl` | Live request rows, provisional Estimated Cost |
| `docker logs -f`, then `<run-dir>/host/stdout.log` and `stderr.log` | Activity, stderr and raw tabs; Claude subscription usage readings |
| `<run-dir>/snapshots.json`, workspace git history | Workspace tab |
| `batches/<id>.toml` and `batches/state/<id>.json` | Queued runs and Batch status |
| Login Pool directories under the state root | Enrolled Login Profiles and pending login journals |
| A Login Profile's stored login (`secret.json`) | The values its login plugin redacts, so live lines can be redacted; nothing derived from it is shown |
| A live Codex rollout under a busy Login Profile's `plugin/work/sessions/` | Codex subscription usage readings, the `rate_limits` field only |
| Results Repo `results/` and `exclusions/` | History, Exclusions, past durations, recorded subscription usage readings |

The monitor reads Results Repo files directly and caches each record by modification time, never through `runs.jsonl` (grilling 2026-10-07).
A Login Profile's `plugin/work` directory sits beside its live credentials, so the monitor reads nothing there except the `rate_limits` field of Codex rollout lines.

### Run stages

A live run is in exactly one stage (grilling 2026-10-07):

| Stage | Observation | Shown as |
| --- | --- | --- |
| Starting | Its runner holds `.runner.lock`, its container has not started, and no `host/host-result.json` exists | ◌ |
| Running | Its runner holds `.runner.lock` and its container is up | ▶ |
| Grading | Its runner holds `.runner.lock`, its container has stopped or been removed after execution, and no `run-record.json` exists | ⚖ |
| Needs recover | `run-input.json` exists, no `run-record.json` exists, and no runner holds `.runner.lock`, even when its container is still up | red, top of the running pane |

A runner killed outright leaves its detached container running with nothing to harvest it, so a container without its runner needs recovery rather than counting as running.
Lock ownership comes from the kernel's lock table, never from taking the lock: a probe that held the lock even briefly could make a starting recovery refuse the run; where the table is unavailable the stage shows as unknown.

A run with a `run-record.json` is finished and belongs to history.

### Candidate display

A Benchmark Candidate is shown as `name · model · effort`: the Construct Definition's `name` and its `CONSTRUCT_MODEL` and `CONSTRUCT_EFFORT` runtime environment values, with `—` for a missing value (grilling 2026-10-07).
A Construct Definition's name alone does not identify a configuration, since one name has been built with different models and efforts, and every rebuild changes the Candidate Hash.
Secondary labels, shown dimmed, are the first eight characters of the Candidate Hash and the image's recipe revision.

### Dashboard

The dashboard has three panes: a narrow status pane across the top, the running pane filling most of the bottom left, and a narrow queued pane on the bottom right.
Live panes refresh every two seconds by default (`--interval`).

The status pane shows (grilling 2026-10-07):

- the resolved locations and their sources, and the Results Repo clone's last fetch time and how many commits it is behind its remote-tracking branch, both from local refs;
- counts of queued runs, live runs (running plus grading), and runs finished in the last seven days, with the all-time total dimmed;
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
Claude reports one in its `rate_limit_event` stdout lines (the `seven_day` window); Codex reports one in its rollout `rate_limits` (the window of 10080 minutes).
The monitor takes the newest reading for a Login Profile from its live run's output, else from the Run Records that name that Login Profile.

| Situation | Shown value |
| --- | --- |
| A reading exists and its reset time has not passed | The reading's utilization, plus the Estimated Cost observed on the Login Profile after the reading divided by the provider's rate, marked `≈` when that addition is nonzero |
| A reading exists and its reset time has passed | The Estimated Cost observed on the Login Profile since the reset, divided by the provider's rate, marked `≈` |
| No reading exists | The Estimated Cost of the Login Profile's runs over the last seven days, divided by the provider's rate, marked `≈` |

Live runs count with their provisional Estimated Cost, and excluded runs count too, since an Exclusion does not undo spend.
A value from a reading shows its reset time, as in `41% · resets Thu 14:00 · read 12m ago`.

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
