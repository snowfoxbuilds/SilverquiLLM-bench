Status: DRAFT

Last updated: 2026-10-08

# Run Monitoring

`silverquillm top` is a terminal monitor over this host's live Benchmark Runs, the batch queue, the Login Pools, and the Results Repo's history; the only thing it changes is a Login Cooldown the operator asks for.

## Context

The scheduler and `silverquillm run` print nothing while a run is in progress, and the previous `top` showed only batch counts.
An operator needs to see what is running, what it costs, how close each Login Profile is to its weekly subscription limit, what is queued, and how past runs went, without reading run directories by hand.
This page replaces the historical image-run artifact and telemetry spec; that layout is recoverable from git history, and [Benchmark Runner](BENCHMARK-RUNNER.md) keeps the legacy runner overview (grilling 2026-10-07).

## Design

### Command and scope

`silverquillm top` opens the monitor; `silverquillm queue ls` stays the scriptable one-shot queue listing (grilling 2026-10-07).
The monitor is a Textual application shipped as the optional `monitor` extra (`silverquillm-bench[monitor]`), so grader and candidate environments never install it; without the extra, `top` prints a one-line install hint.
Without a terminal, `top` draws nothing and points to `queue ls`.

The monitor is read-only with one exception (grilling 2026-10-07).
It never takes a lock that a runner or the scheduler takes, stops or recovers a run, edits a Batch, or fetches or pulls the Results Repo.
Its one write is a Login Cooldown the operator asks for with a key in the LOGINS pane (2026-10-08): it goes through the same file and validation as `silverquillm login cooldown`, only for an enrolled Login Profile, and touches nothing else of the slot (not its stored login, its lock, or a run holding it).
Stopping a run, recovering, and editing the queue stay CLI and file operations.

Live views cover this host only: its Docker daemon, its run directory, its batch queue, and its Login Pools (grilling 2026-10-07).
History comes from the local Results Repo clone as it stands; runs from other hosts appear once the clone is pulled and show their host label.

### Locations and host configuration

The monitor resolves the Results Repo, batch queue directory, run directory, and state root exactly as every Karn command does, through the host configuration described in [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md#operator-entrypoints-and-records).
The STATUS pane names each resolved location and the source it came from (flag, environment, or configuration file).

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

The Results Repo has no index, so the monitor reads its records directly and caches each one by modification time (grilling 2026-10-07).
A Login Profile's `plugin/work` directory sits beside its live credentials, so the monitor reads nothing there except the `rate_limits` field of Codex rollout lines.

### Run stages

The monitor follows every run on this host that has a run directory or a run container, and puts each in exactly one stage (grilling 2026-10-07).
A run directory and a run container are one run when the directory's path, taken under its resolved parent, is the container's bind source, so a relative or linked run root still yields one row per run; a linked run directory itself is never followed.
A stage comes from these observations, never from a record's existence alone:

| Observation | Source |
| --- | --- |
| Owner | Whether a process holds the run's `.runner.lock`; the runner and `silverquillm recover` both hold it, so it is read from the kernel's lock table and never taken |
| Container | Whether `sq-run-<run-id>` is running, stopped, or absent |
| Retained record | The original `run-record.json`, and any linked recovery `recovery-N/run-record.json` whose `recovery_of` names the run and whose writers were confirmed stopped |
| Final record | A linked recovery, retained or published and named by `recovery-record.json`, or an original whose `execution.workspace_stopped` is true; an original with `workspace_stopped: false` is an unconfirmed observation and never final |
| Publication | Whether each retained record is published: a record in the Results Repo under its Candidate Hash and run id whose own identity matches that location; unknown when no Results Repo is resolved |
| Pending login | Whether a Login Profile's pending login journal names the run |

The first matching row decides the stage:

| Stage | Rule | Shown as |
| --- | --- | --- |
| Finished | No owner holds the run, or ownership is unknown, a final record exists, every retained record of the run is published (or no Results Repo is resolved), and no pending login journal names the run | not shown; the run belongs to history |
| Unknown | The kernel's lock table cannot be read | `?`, with the Needs recover reasons that would apply |
| Starting | An owner holds the run, no record is retained, its container has not started, and no `host/host-result.json` exists | ◌ |
| Running | An owner holds the run, no record is retained, and its container is running | ▶ |
| Grading | An owner holds the run, no record is retained, and its container has stopped or been removed | ⚖ |
| Recording | An owner holds the run and a record is retained: the runner or a recovery is publishing, settling its login, or reconciling an unconfirmed stop | ✎ |
| Needs recover | No owner holds the run | red, top of the running pane |

Ownership comes from the kernel's lock table, never from taking the lock: a probe that held the lock even briefly could make a starting recovery refuse the run.

Every record, retained or published, counts only when it passes the Run Record's own validation, read from regular files within a size bound and cached by file identity.
A record that fails it, or a directory without a valid record, establishes nothing: it is never final and never published.

A Needs recover row names every reason that applies, and whether the run's container is still running:

| Reason | Meaning | What `silverquillm recover` does |
| --- | --- | --- |
| No record | The runner died before retaining a record; a detached container may still be running with nothing to harvest it | Stops the workload on request, grades once, and publishes |
| Unconfirmed stop | The only record is an original with `workspace_stopped: false` and no linked recovery | Stops the workload, settles the login, grades once, and retains and publishes a linked recovery; the original stays unchanged |
| Unpublished | A retained record, original or linked recovery, is missing from the Results Repo, though its scores may be final | Publishes the same retained record under the same id, without grading again |
| Login settlement pending | A pending login journal still names the run, so its login harvest failed or was interrupted | Settles that login under the login lock, preserving the run's native sessions first |
| Unreadable record | A retained record, original or linked recovery, fails validation | Refuses the run until the record is repaired |
| Mismatched record | The retained original names another run | Refuses the run (`recovery_run_identity_mismatch`) |
| Ambiguous linked recovery | More than one linked recovery is retained | Refuses the run (`ambiguous_retained_recovery`) |
| Unreadable published record | The Results Repo holds a directory for the record that is not a valid record of that identity | Refuses to read it until it is repaired |
| Ambiguous published record | With no retained record, more than one published record carries the run id | Refuses the run (`ambiguous_interrupted_run_record`) |

A linked recovery that is retained, published, and settled makes the run Finished, so the original's unconfirmed record stops raising a warning while staying unchanged in history.
A run directory with no `run-input.json`, no retained record, and no owner never launched; recovery has nothing to settle, so the monitor ignores it.
With no local retained record, the run's only published record decides: final when its `workspace_stopped` is true, otherwise an unconfirmed stop.
A run whose records cannot be read, are misplaced, or are ambiguous is shown as Needs recover with the error, since `recover` would refuse it too.

These cases must hold:

| Case | Stage over time |
| --- | --- |
| A normal run | Starting, Running, Grading, Recording while its record is published, then Finished |
| The runner is killed while the workload runs | Needs recover (no record), with the container still running |
| A record retained with `workspace_stopped: false` | Needs recover (unconfirmed stop) until a linked recovery is retained and published, then Finished |
| A record retained but not yet published | Needs recover (unpublished), even with final scores, until `recover` or a scheduler pass publishes it |
| A failed login harvest after a published, stopped record | Needs recover (login settlement pending) until settlement succeeds, then Finished |
| A recovery in progress | Recording while it holds the run, then Finished, or Needs recover with whatever it left unfinished |
| Only a published record, stopped or not | Finished, or Needs recover (unconfirmed stop) |
| An empty or misfiled Results Repo directory | Needs recover (unreadable published record) |
| A record missing its scores or naming another run | Needs recover (unreadable record, or mismatched record) |
| A malformed linked recovery beside an unconfirmed original | Needs recover (unreadable record) |

### Candidate display

A Benchmark Candidate is shown as `name · model · effort`: the Construct Definition's `name` and its `CONSTRUCT_MODEL` and `CONSTRUCT_EFFORT` runtime environment values, with `—` for a missing value (grilling 2026-10-07).
A Construct Definition's name alone does not identify a configuration, since one name has been built with different models and efforts, and every rebuild changes the Candidate Hash.
Secondary labels, shown dimmed, are the first eight characters of the Candidate Hash and of the image's recipe revision, a full commit id (2026-10-08).
Run details show the recipe revision whole.

### Dashboard

The dashboard's top row holds the STATUS pane, a single column on the left, and the LOGINS pane, which takes the larger share of the width; below them the running pane and then the queued pane each span the full width (2026-10-08).
Below 150 columns the STATUS column narrows, cutting long paths, and the two top panes stay side by side.
Live panes refresh every two seconds by default (`--interval`).
Reads run off the interface thread, one at a time: a refresh asked for while one is reading runs once after it, however many ticks or `r` presses arrived, so a slow Docker daemon delays the view rather than piling up reads.
Every read the app starts reports back exactly once, whether it read, was skipped as stale, or failed, so a read that fails or goes stale never stops later ones.
The reads run on the app's own daemon threads, never the event loop's default executor, so the process exits without waiting for a read in flight.
Quitting stops new reads, tells the monitor's followers to end their `docker logs` without waiting for them, and closes the monitor on the last read's own thread, or at once when none is in flight.

The STATUS pane shows, one above another (grilling 2026-10-07):

- the resolved locations and their sources, this host's label, and the Results Repo clone's last fetch time and how many commits it is behind its remote-tracking branch, both from local refs;
- counts of queued runs, live runs (every stage but Finished), and runs finished in the last seven days, with the all-time total dimmed.

The LOGINS pane shows each Login Pool under its own header with its untapped count, then one line per Login Profile: a free, busy, pending or cooling-down marker, a usage bar, and its Estimated Weekly Usage with reset time and reading age (2026-10-08).
A profile with a pending login journal names the run that owns its settlement before its usage.
The pools sit side by side, one column each, so six profiles a pool fit in the height of the STATUS pane.
The pane takes the fullest form that fits the width uncut: usage bars and full wording, then without the bars, then with the wording shortened (`41% · Thu 14:00 · 12m ago`); failing those, the form that fits by cutting only profile names.
When no form fits two columns, the pools stack and the pane scrolls, as it does whenever a pool has more profiles than its height.

A Login Profile under a Login Cooldown shows its own marker and colour and reads `cooldown until Thu 14:00 (3h12m)` before its usage (grilling 2026-10-08).
A pool's untapped count counts only profiles a new run could take now: not busy, not pending, and not cooling down.

Each pool takes the keyboard focus in turn, and the focused pool marks its selected profile; the pane scrolls to keep it in view (2026-10-08).
`t` holds the selected profile for one more hour: an hour from now, or an hour past a cooldown already in force, so each press adds an hour.
`c` ends the selected profile's cooldown ten seconds from now rather than at once, and does nothing but say so when it has none.
Each write refreshes the view at once and says what it set; a write that fails says why and changes nothing.

Each running-pane row shows the stage, benchmark, Candidate display, Login Profile, a progress bar with its Estimated %, elapsed container time with the budget beside it, Estimated Cost, and a cost sparkline.
The progress bar is the Estimated %, not the share of the budget used: a run is measured against how long past runs took, and the budget is only the limit it stops at (grilling 2026-10-08).
With no past runs to measure against there is no bar, only the elapsed time and budget.
A Needs recover or Unknown row shows whether its container is up or stopped, then its reasons, in place of the progress bar.
Selecting a row opens its run details.

**Estimated %** is the elapsed container time divided by the median container duration (`stopped_at` minus `started_at`) of completed, non-excluded runs of the same benchmark (grilling 2026-10-07).
Those runs are the same Candidate Hash's when it has any, and otherwise the same Candidate display's.
The figure stays at most 99% while the run is live and is blank when no such run exists.

**Estimated Cost** is provisional until the run has a record, then the record's own (grilling 2026-10-07).
The provisional figure comes from the run's live telemetry events and is marked `~`; with native telemetry off it is blank.
Codex request events are priced with the bench's price table, as at the end of a run.
Claude request events lack the cache-write duration split that the price table needs, so Claude runs sum Claude Code's own per-request `cost_usd`, charging one logical request (`request_id`) once even when it is observed again; a repeat that disagrees is counted as a conflict, and an event without a request id stands alone.
Once a valid record applies to the run, the row shows that record's Estimated Cost, its completeness, and its priced requests, without waiting for publication or for history to refresh.
The applicable record is a linked recovery before the original, and a locally retained copy before a published one; a missing recorded cost stays missing rather than falling back to the live figure.
A recorded figure drops the `~`, carries `*` when its record calls it incomplete, and shows `≠N` for N conflicting request observations.

The queued pane lists the not-yet-started run specs in execution order, under one header line per Batch (grilling 2026-10-07).
Each run takes one line with its benchmark, budget and Candidate display; a queued run has no Login Profile until it launches.
A Batch's header line shows its countdown to `not_before`, or `⚠ needs ack` for a Batch with no committed state, and how many of its runs have started.

### Estimated Weekly Usage

Each Login Profile shows its Estimated Weekly Usage and how old the underlying observation is (grilling 2026-10-07).

A subscription usage reading is a provider's own report of the weekly window: a utilization percentage, a reset time, and when it was observed.
Claude reports one in its `rate_limit_event` stdout lines (the `seven_day` window); Codex reports one in its rollout `rate_limits`, as whichever of its windows lasts 10080 minutes (see [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md#efficiency-measurements)).
The monitor takes the newest reading for a Login Profile from its live run's output, else from the Run Records that name that Login Profile.
A reading seen live is kept in memory for its Login Profile after its run ends, since the run's record may hold only an untimed copy of it; a newer reading replaces it, and it is dropped once it can no longer anchor a value.

A reading speaks for its own weekly window, and for one window after that at most:

| Situation | Shown value |
| --- | --- |
| The newest reading's reset time has not passed | The reading's utilization, plus the Estimated Cost observed on the Login Profile after the reading divided by the provider's rate, marked `≈` when that addition is nonzero |
| The newest reading's reset time has passed, less than seven days ago | The Estimated Cost observed on the Login Profile since that reset, divided by the provider's rate, marked `≈` |
| The newest reading's reset time passed seven days ago or more, or no reading exists | The Estimated Cost observed on the Login Profile over the last seven days, divided by the provider's rate, marked `≈` |

A newer reading always replaces whatever an older one implied.
Only a value from an unexpired reading shows a reset time; after the reset, the provider's next reset is unknown, so none is shown.

Only this host's records count toward its Login Profiles, since a Login Profile is host-local and another host's identically named slot is a different login.
A record is this host's when it is retained in this host's run directory, or when its provenance names this host's label, resolved as run provenance resolves it (`SILVERQUILLM_HOST_LABEL`, else the hostname's first label).
A record without host provenance stays in history but never counts toward local usage, and a record naming only a slot, from before Login Pools, is matched to this host's Login Profile of that slot.

A record supplies a reading or spend only when it passes the Run Record's own validation and, when published, is filed under its own identity; history still lists the rest.

Each execution's spend counts once.
A linked recovery reconciles its original's execution without running the model again, so of an execution's records only one counts.
For a run with a directory on this host that is the record its own row applies, Finished or not, so the row and its Login Profile agree; otherwise a stopped linked recovery counts before its original.
A live run counts its applicable record once it has one, and its provisional Estimated Cost before that.
Excluded runs count too, since an Exclusion does not undo spend.

A Claude reading retained in a record has no time of its own; the run's container stop bounds it.
Such a reading counts spend only after that stop, so spend between the reading and the stop is missing: its value is always marked `≈`, and its age is shown as a lower bound, as in `read ≥3h ago`.
When the same reading was also seen live with a time, the timed observation is used.
A value from an unexpired reading reads like `41% · resets Thu 14:00 · read 12m ago`.

### Historic view

The historic view browses by benchmark, by Candidate display, or by run (grilling 2026-10-07).
Selecting a benchmark or a Candidate display lists its runs; a Candidate display expands to its individual Candidate Hashes.

A run occupies one line: run date, benchmark, Candidate display, execution status, container duration over budget, target-card pass rate with passed/total, FDN Card Regression pass rate, Engine Regression pass rate, Estimated Cost, Agent Turns, total tokens, Login Profile, host label, and the short run id.
Every column sorts.
Excluded runs are dimmed with their reason code, and a key hides them.
Combined Regression joins the line once records carry it.
A line is one Run Record, identified by where it is stored: two published records can share a run id under different Candidate Hashes, and both stay listed, each opening as itself.
Selecting a run opens its run details.

### Run details view

The header carries `◉ LIVE` or `◼ HISTORICAL`, the stage for a live run, the Candidate display and secondary labels, Login Profile, timings, scores, Estimated Cost with its breakdown, Agent Turns, and token usage, each as available (grilling 2026-10-07).

| Tab | Content |
| --- | --- |
| Activity | The candidate's stdout event stream rendered for reading: assistant text, tool calls with their commands, shortened tool results |
| Stderr | The candidate's stderr |
| Requests | One row per model request with model, token types, and cost, and a cost sparkline |
| Workspace | The agent's commits, read from the workspace's reflog as a file since no git command runs in a candidate-controlled repository, and the snapshot timeline with files changed per snapshot |
| Raw | Unrendered stdout |

A Needs recover or Unknown run's header also names its reasons and whether its container is up.
A live run's header shows the same progress bar and Estimated % as its dashboard row, with the budget as text beside the elapsed time.

A live run's tabs follow `docker logs -f` and the events file; a historical run's tabs read the retained files.
Opening a run clears every tab, table, sparkline and the header first, and they show loading or unavailable until that run's own evidence arrives: nothing of the previously shown run appears under another run's header.
The header's record facts, the Requests tab and the cost breakdown all come from one applicable Run Record, the one the dashboard applies to the run.
Any other run follows the record the monitor applies to its execution on each refresh, live or Finished, a retained copy awaiting publication or a linked recovery included, so a recovery that finishes entirely between two refreshes still replaces its original; the last applied record is kept only for a refresh that could not read one, and telemetry supplies requests only while no record applies.
When another record comes to apply, such as a linked recovery replacing its original, everything the old record supplied is cleared and a fetch made for it is ignored.
A record opened from history stays that record, found by its stored location, so an original keeps showing as the original; this host's live view, logs and workspace accompany it only when this host's run under that run id was launched for the record's Candidate Hash.
A run that leaves the live view reads its retained logs once, even when this host has none, and the applicable record's detail is asked for on every refresh until it reads: its summary can reach the history after the run finishes, and a record file can be briefly unreadable.
Each stream keeps its own newest 4000 lines in its tabs, so a flood of stderr never evicts stdout from Activity and Raw.
Everything taken from a run, its records or its workspace is drawn as literal text, never as markup, and an out-of-range or non-finite number in candidate output, telemetry or a record (a count above 10^15, a time no date can hold, a negative or wrong-typed value) is shown as unknown rather than as zero, while the request it belongs to still counts.
Live Docker logs are unredacted, so the monitor applies the login plugin's redactions to every line before showing it.
Those redactions are the Login Profile's stored login when the follow starts, so a token the candidate refreshes mid-run is redacted only from the retained logs, which the host redacts with the refreshed values at capture.
A followed run keeps its newest 2000 lines, each cut at 16 KiB.
The native transcript is not shown: for Claude it largely duplicates stdout, and it sits beside the Login Profile's credentials.

### Navigation

Every action has a key, and the mouse is a convenience on top: a terminal reached through mosh and a multiplexer may not deliver clicks at all (grilling 2026-10-08).
`?` lists every key over the current view, and the footer names the keys of the view in front.

| Keys | Where | Action |
| --- | --- | --- |
| `1` `2` `3`, or a click on a view tab | everywhere | dashboard, historic view, run details |
| Tab, Shift+Tab | everywhere | move between panes and tables |
| arrows, PgUp, PgDn, Home, End | everywhere | move within, or scroll, the focused pane |
| Enter, or a click on a row | dashboard, history | open the selected run |
| ↑ ↓ or `k` `j`, or a click on a profile | LOGINS pane | select a Login Profile |
| ← → or `h` `l` | LOGINS pane | the other pool, or the neighbouring pane |
| `t` | LOGINS pane | hold the selected profile one more hour |
| `c` | LOGINS pane | end the selected profile's cooldown in ten seconds |
| Escape | run details | back to the view it was opened from |
| `r` | everywhere | refresh now |
| `?` | everywhere | the key list |
| `q` | everywhere | quit |
| `b`, `l` | history | focus the browse tree, the run list |
| Enter, Space | browse tree | show that benchmark, candidate or hash; expand or collapse |
| `s` or `>`, `<`, or a click on a column header | history | sort by the next or previous column |
| `S` | history | reverse the sort |
| `x` | history | hide or show excluded runs, which otherwise sit dimmed beneath the included ones |
| `[`, `]`, or a click on a tab | run details | previous or next tab, whose log or table then takes the keys |

`--no-mouse` leaves the mouse to the terminal, for selecting text.
The monitor asks the terminal for mouse reports in character cells only, never in pixels: a multiplexer reached over mosh may offer pixel reports without knowing the real pixel size, which puts clicks in the wrong place.

### Look and feel

The monitor is a dense operations console with Magic: The Gathering flavour (grilling 2026-10-07): tapped and untapped glyphs for busy and free Login Profiles, a mana colour per provider, set-symbol-style benchmark badges, and sparklines.
Every colour, glyph, and border lives in one theme definition, so the look changes without touching the views.
The default theme reads on a 256-colour terminal, and `--no-flair` selects a monochrome, plain-glyph theme.
Glyphs are single-cell characters, so columns stay aligned in any terminal font.
Pass rates take a rarity colour: mythic from 90%, rare from 70%, uncommon from 40%, common below.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-012](../adr/ADR-012-independent-host-for-karn-benchmark-candidates.md) | Karn v4 execution and observations have an independent consumer contract |
| [ADR-014](../adr/ADR-014-silverquillm-runs-karn-constructs-without-ozolith.md) | The Karn commands, `top` among them, own the top level |
