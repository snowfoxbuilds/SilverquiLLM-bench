# Karn benchmarking

Build once, select a local subscription login, and collect benchmark data with the `silverquillm` commands.
Python 3.13 is required by the current stock login-plugin wheel closure.
The installed benchmark package needs Docker and its own Python dependencies; Karn is used separately to build the candidate, and no Ozolith package is involved.

## Build and enroll

The checked-in [bare Codex example](../examples/karn/constructs/bare-codex/construct.toml) selects `gpt-6-astra`, Codex 0.153.4 through `codex@1`, and the stock Codex login plugin.
It carries no custom skills or polling controller.

```bash
karn build examples/karn --worktree --out /tmp/bench-codex-build
silverquillm login benchmark --build-output /tmp/bench-codex-build --construct bare-codex
```

`--worktree` explicitly builds the supplied example files and records the producer's dirty-source provenance.
For committed Config Repo builds, point Karn at that repository without `--worktree`.
Build output and the exact local image must remain available; queued execution never rebuilds or pulls an image.
Enrollment uses the host's Codex CLI in an isolated home, through Karn's existing plugin.
Use the same profile name and state root for direct runs and batches; a host-local lock prevents simultaneous refreshes of that login.
A direct run refuses a login another runner holds (`login_in_use`) without creating a run; a batch leaves that entry pending and retries it on its next pass.

A run interrupted while its login was mounted leaves a pending refresh that only the plugin artifact which mounted it may settle.
Switching to a build with a different login plugin then fails with `login_recovery_requires_previous_plugin`.
Settle it first with `silverquillm recover RUN_ID`, naming the run in `<state-root>/logins/<profile>/active.json`; recovery uses that run's retained plugin artifact.

## Build the grader

```bash
silverquillm grader build
```

Grading imports and runs the agent's engine and cards, so it happens only in this bench-owned image: pinned base image and hashed pytest requirements, no network, your UID, a read-only root, dropped capabilities, memory and process limits, and read-only mounts of only the selected workspace, SilverquiLLM, and the grading inputs.
`run`, `scheduler`, and `recover` refuse before launch with `grader_image_unavailable` when the image is missing; they never build or pull it.
`--grader-image` (or `SILVERQUILLM_GRADER_IMAGE`) selects another local tag, and `--grading-timeout` (default 3600 seconds) bounds a grading pass.
A timed-out or failed grading pass records absent scores with `grading_container_failed:<reason>`, never zero, and each record's `grading_isolation` names the grader image ID.
Isolation protects the host, not score integrity: candidate code shares the pytest process that counts its results.

## Run and inspect

```bash
silverquillm run --build-output /tmp/bench-codex-build --construct bare-codex --benchmark smoke --login benchmark --results-repo ./private-results
silverquillm run --build-output /tmp/bench-codex-build --construct bare-codex --benchmark hob-medium --login benchmark --results-repo ./private-results
```

Use `--bench-root` when launching outside the benchmark checkout.
`--budget-seconds` defaults to 86400; the supplied definition must allow at least that much time.
The budget begins at container start, including initialization.
There is no `basic`/`planned` option: benchmark files supply task and planning guidance.
The selected cards and any engine changes are the requested implementation.
`--native-telemetry codex` requires native Codex journals and the OTel relay, and refuses a definition without `CODEX_HOME`; `none` disables them.
The default `auto` enables them when the definition declares `CODEX_HOME`, because the v4 definition has no telemetry field; batch entries accept the same `native_telemetry` key.
A `restricted` network runs its egress proxy with the candidate image's own `python3`; an image without it is refused before launch with `restricted_network_requires_python3`.

Each run retains its workspace, snapshots, stopped final workspace, grading-source decision, selected definition and plugin artifacts, sanitized observations, and independent grades under `runs/karn/<run-id>/` by default.
The immutable schema 2 record lives under `private-results/results/<candidate-hash>/<run-id>/`.
Estimated cost is API-equivalent USD, not the subscription bill.
Agent turns count model responses plus tool calls; missing measurements remain null with an explanation.
FDN coverage lists tested and uncovered cards explicitly.
Run metadata fingerprints the actual host grading suites, test helpers, and replay identity maps; unavailable hashes remain explicit observations.

After the host confirms that workspace writers stopped, successful collection preserves the final workspace.
A missing or incomplete collection is recorded with its reason.
`git-history.bundle` preserves the trusted staging commit and available agent commits through a fresh host-owned repository; candidate hooks, remote credential configuration, and object alternates are excluded.
`git-history.json` explains a missing or incomplete history artifact.
If its engine cannot load, grading can use a retained usable snapshot; `grading-source.json` records the reason and chosen source.
Symlinks, files over 32 MB, and non-regular files are never copied; they are listed as `omissions` and do not disqualify a workspace.
Only an unreadable `engine/`, `cards/`, or `test_utils.py` source is an `error` that sends grading to an earlier snapshot.
A failed process, deadline, or interruption still permits grading after the host confirms that workspace writers stopped.

Telemetry normally reaches the host through the run's restricted Docker relay.
`--collector-host` can select the local bind address reachable from Docker when automatic hostname/bridge detection does not fit the host's topology.
Only the relay's fixed telemetry POST route is available in addition to the definition's allowed HTTPS hosts.

## Batches

Write `batches/hob-learning.toml`:

```toml
format = "karn-v4"

[[runs]]
build_output = "/tmp/bench-codex-build"
construct = "bare-codex"
benchmark = "hob-medium"
login = "benchmark"
budget_seconds = 86400
```

```bash
silverquillm scheduler --once --replay-without-state hob-learning --results-repo ./private-results
silverquillm queue ls
silverquillm top
```

The first invocation acknowledges the missing state for that one new batch.
Subsequent invocations resume from the recorded cursor; omit the acknowledgement flag.
Entries execute serially in file order, and later entries are reread before starting.
An optional timezone-aware `not_before` applies to a whole batch.
Failed entries retain their data and the scheduler continues.

A run left active by a crashed scheduler is recovered before further execution.
Recovery confirms that its container has stopped, removes only resources carrying that run's ownership label, preserves available measurements/workspace, and records the interrupted outcome without replaying the model task.
Keep both batch state and local run artifacts for this recovery.
If an immutable record already exists but its writers were unconfirmed, successful reconciliation appends a linked recovery observation and preserves the original record bytes.
The index and queue expose `recovery_of` and `execution_run_id` so this additional observation is distinguishable from another model execution.
Each host maintains its own queue and login state.
A scheduler interrupted before a run wrote its `run-input.json` never launched that run; the entry is recorded as failed with `interrupted_before_launch` and the batch continues.

`silverquillm recover RUN_ID` recovers a direct run the same way, from its retained artifacts and without the candidate image.
It refuses a run whose container is still running unless `--stop` is given, and refuses a run another process is still executing.
Recovering an already recovered run returns the existing record.
SIGTERM and SIGHUP interrupt `run`, `scheduler`, and `recover` like Ctrl-C, so the workload is stopped and the interrupted outcome recorded; a grading or probe container in progress is killed and removed rather than left running.

### Recovery guarantees

- Recovery never runs the workload again, never needs the candidate image, and never changes a published record.
- A record is retained in the run directory before it is published: `run-record.json`, or for a linked recovery `recovery-N/run-record.json`, which recovery finds by directory name and never through a path read from a file.
  Record writes wait up to 120 seconds for concurrent writers; on timeout, `recover` or a later scheduler pass publishes that same retained record under the same id, without recovering or grading again.
- Authentication is settled separately from the record.
  A run whose login harvest failed (`login_harvest_failed` or `login_harvest_pending` in its execution) still owns the profile's pending login after its record is written.
  Before `recover` returns any stopped record, it checks whether this run owns the pending login and, if so, settles it under the login lock with the exact plugin artifact retained in the run directory, preserving the run's native sessions into its own evidence first.
- Recovery never settles or harvests another run's pending login: that run's container may still be live, and its native state belongs to that run's own evidence.
  Recovering that run, or the login's next run, settles it.
- Settlement never blocks publication.
  If it fails for any reason, a busy login included, the record is still published and the pending login is kept; `recover` prints the final record and exits non-zero with `login_settlement_pending:<reason>`.
  Run `recover` again once the cause is fixed.
- In a batch, a recovered row keeps its execution status and recovery linkage, and is marked `record_write_pending` or `login_settlement_pending` until a later scheduler pass finishes publication or settlement.
  These retries read only the batch state, so they continue after the batch file is removed, and the batch's other entries keep running.

### Records affected by the former scheduler bug

Before this fix, a scheduler that hit a busy results repository while recovering a running row marked that row `failed` with `recovery_failed:record_write_pending` and never published its record.
To find affected rows:

```bash
grep -l 'recovery_failed:record_write_pending' batches/state/*.json
```

For each such row, run `silverquillm recover RUN_ID` with the same `--results-dir`, `--results-repo`, `--state-root`, and `--bench-root` the scheduler used.
A plain recovery publishes the retained `run-record.json` unchanged.
A linked recovery never wrote its link, so `recover` reconciles the run once more and publishes a single linked record; the earlier unpublished `recovery-N/` directory stays as evidence and is never published.
Neither path replays the model task.
The batch state row is not rewritten and still reads `failed`; the published record is authoritative for that run's outcome.

## Reading results

- The stub workspace already passes 14 of hob-medium's 69 target cases, so read card correctness against that floor.
- `fdn_regression.complete` is always false on hob-medium because the coverage ledger lists uncovered FDN cards; filter on the coverage fields instead.
- The Test Harvester reads only records that point into the historical `docker/` tree, so Karn records do not yet feed agent-test promotion.

## Historical records

Schema 1 records and their identities, including `legacy` and `ozolith-v1`, keep their existing meaning and stay readable without Ozolith; every `ozolith-v1` record carries its vendored bundle.
The shared reader and index accept both schemas; new rows do not invent a historical mode or leaderboard flag.
Candidate Bundles can no longer be run, promoted, or published; rebuild an old candidate as a Karn construct to run it again.
Batch files and state in the Candidate Bundle format are shown as unsupported and never run or rewritten.
`legacy resume` replaces a prior leg's `prompt.md` and `run_manifest.json` with fresh files instead of writing through links, and refuses a prior leg whose `prompt.md` is a link or whose `workspace_final` holds a FIFO, socket, or device.
The historical `--image` lineage remains under `silverquillm legacy`; `legacy rescore` grades with the authoritative `test_utils` in an isolated copy, so re-grading an old run can change its numbers without touching stored records.
