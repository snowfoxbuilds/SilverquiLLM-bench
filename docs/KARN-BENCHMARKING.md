# Karn benchmarking

Build once, select a local subscription login, and collect benchmark data with the `silverquillm` commands.
The installed benchmark package needs Docker and its own Python dependencies; Karn is used separately to build the candidate, and no Ozolith package is involved.
Run `silverquillm` from a Python 3.13 environment: the stock login plugin's wheel closure needs CPython 3.13, and the plugin is installed with the interpreter `silverquillm` itself runs on (or a `python3.13` on `PATH`).

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e .
source .venv/bin/activate
```

## Build and enroll

The candidate recipes live in the results repository, beside the records they produce: `karn/constructs/<label>` in bench-results is a Karn Config Repo, so any host with that repository can rebuild the same candidates.
Build from its committed tree, without `--worktree`, so every image's `karn.config.revision` label names the recipe commit behind its records:

```bash
karn build ~/bench-results/karn --out ~/bench-builds/roster-1
silverquillm login --build-output ~/bench-builds/roster-1 --construct bare-codex
```

The current batch (2026-09-28) runs every model at effort `medium` with subagents disabled. The bench does not enforce either, so candidates stay generic.

| Construct | Model | CLI |
|---|---|---|
| `bare-codex` | `gpt-6-astra` | Codex 0.157.1 |
| `bare-codex-luna` | `gpt-6-luna` | Codex 0.157.1 |
| `bare-codex-sol` | `gpt-6-sol` | Codex 0.157.1 |
| `bare-claude-opus` | `claude-opus-5-5` | Claude Code 2.1.284 |
| `bare-claude-sonnet` | `claude-sonnet-5-5` | Claude Code 2.1.284 |
| `bare-claude-fable` | `claude-fable-5-1` | Claude Code 2.1.284 |
| `bare-claude-haiku` | `claude-haiku-4-5`, no effort setting | Claude Code 2.1.284 |

Claude recipes bake a managed-settings file that denies `Agent` and `Workflow`.
Codex recipes bake `/etc/codex/config.toml` with `[agents] enabled = false` (and `multi_agent = false`). The `[agents]` switch is needed on Codex 0.157.1, where the GPT-6 model catalog keeps the collaboration tools whatever the `multi_agent` feature says.
The Codex recipes also request the Flex tier (`service_tier = "flex"`) as a cost-saving trial, which is why `bare-codex` moved to Codex 0.157.1: 0.153.4 sends only the tiers a model's catalog lists, and astra's lists only Fast. Whether the ChatGPT backend honors Flex shows only in usage, since costs are reported at standard rates.
Each record's `subagent_threads` measurement counts the agent threads beyond the main one (Claude sidechain transcripts, Codex threads other than the task's), so a batch meant to run without subagents should show `0`.
The count is an observation, not an incompleteness reason.
The Codex recipes pin their CLI with their own `[image.native_cli]`; 0.157.1 needs a Karn that accepts that release's extra resource files (snowfoxbuilds/ozolith#515).
Each construct carries no custom skills or polling controller.

Build output and the exact local image must remain available; queued execution never rebuilds or pulls an image.
Enrollment uses the host's Codex CLI in an isolated home, through Karn's existing plugin.
Each construct has its own login in `<state-root>/logins/<construct>`, enrolled once and kept across rebuilds of that construct; enroll every construct you run, and use the same state root for direct runs and batches.
Constructs never share a login, so they can run at the same time, while a host-local lock prevents simultaneous refreshes of any one construct's login.
A direct run refuses a login another runner holds (`login_in_use`) without creating a run; a batch leaves that entry pending and retries it on its next pass.

### Claude constructs

The Claude constructs run Claude Code 2.1.284 through `claude@1` on a Claude subscription, with the stock `karn-claude-login` plugin.
Their egress allows `api.anthropic.com` for inference and `platform.claude.com`, where Claude Code refreshes its subscription token, and they set `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`.

```bash
silverquillm login --build-output ~/bench-builds/roster-1 --construct bare-claude-haiku
```

Enrollment runs the host's `claude auth login` in an isolated config directory, so the login is separate from your own Claude Code session and your `~/.claude` is never copied.
Sign in with the subscription account; on a host without a browser, open the printed URL elsewhere and paste the code back.
The host runs exactly one of `karn-codex-login` or `karn-claude-login` per candidate and refuses any other plugin; `login` refuses a construct without one (`candidate_requires_login_plugin`).

A run interrupted while its login was mounted leaves a pending refresh that only the plugin artifact which mounted it may settle.
Switching to a build with a different login plugin then fails with `login_recovery_requires_previous_plugin`.
Settle it first with `silverquillm recover RUN_ID`, naming the run in `<state-root>/logins/<construct>/active.json`; recovery uses that run's retained plugin artifact.

Candidates need no test tooling of their own.
Every candidate container gets the bench's pinned pytest and pytest-timeout read-only at `/run/silverquillm/test-toolchain`, first on `PYTHONPATH`, so `python3 -m pytest` works on the image's own Python.
The vendored wheels in `silverquillm/karn/candidate_toolchain/` are checked against their hashes before each run and unpacked once under `<state-root>/toolchains/`; a mismatch refuses the run with `test_toolchain_integrity_mismatch`.

## Build the grader

```bash
silverquillm grader build
```

Grading imports and runs the agent's engine and cards, so it happens only in this bench-owned image: pinned base image and hashed pytest requirements, no network, your UID, a read-only root, dropped capabilities, memory and process limits, and read-only mounts of only the selected workspace, SilverquiLLM, and the grading inputs.

Grading runs on the candidate's own Python minor version.
`grader build` builds one image per pinned version, tagged `silverquillm-grader:py3.13` and `silverquillm-grader:py3.14`; `--python 3.14` builds just one.
Before launch, `run` and each batch entry read the version of `python3` in the candidate image, in a sandboxed container with no network or mounts, and select the grader built for that version.
A candidate without `python3` or older than 3.13 is refused with `candidate_python_unsupported`, and a version with no built grader with `grader_image_unavailable`; neither creates a run.
Runs never build or pull a grader.
`recover` grades on the version recorded when the run launched and never runs the candidate image; a run launched before versions were recorded is graded on the 3.13 grader.

`--grader-image` (or `SILVERQUILLM_GRADER_IMAGE`) names another local grader; it must still be one `grader build` made for the candidate's version, or the run is refused with `grader_python_mismatch`.
Every grader, including the 3.13 grader that legacy recovery and the `--image` lineage use, must carry the version label `grader build` sets; an older unlabeled `silverquillm-grader:local` is refused until you rebuild.
`--grading-timeout` (default 3600 seconds) bounds a grading pass.
A timed-out or failed grading pass records absent scores with `grading_container_failed:<reason>`, never zero.
Each record's `grading_isolation` names the grader image ID, the candidate's `candidate_python`, and the `grader_python` it was graded on.
Isolation protects the host, not score integrity: candidate code shares the pytest process that counts its results.

## Run and inspect

```bash
silverquillm run --build-output ~/bench-builds/roster-1 --construct bare-codex --benchmark smoke --results-repo ./private-results
silverquillm run --build-output ~/bench-builds/roster-1 --construct bare-codex --benchmark hob-medium --results-repo ./private-results
```

Use `--bench-root` when launching outside the benchmark checkout.
`--budget-seconds` defaults to 86400; the supplied definition must allow at least that much time.
The budget begins at container start, including initialization.
There is no `basic`/`planned` option: benchmark files supply task and planning guidance.
The selected cards and any engine changes are the requested implementation.
`--native-telemetry codex` requires native Codex journals and the OTel relay, and refuses a definition without `CODEX_HOME`; `claude` does the same for Claude Code and `CLAUDE_CONFIG_DIR`; `none` disables the relay.
The default `auto` enables them for whichever of `CODEX_HOME` or `CLAUDE_CONFIG_DIR` the definition declares, because the v4 definition has no telemetry field; batch entries accept the same `native_telemetry` key.
For Claude Code the relay is configured through the environment (`CLAUDE_CODE_ENABLE_TELEMETRY` and the `OTEL_*` exporter variables, prompts and tool details never logged), since Claude Code reads its exporter nowhere else; the host sets only those variables, and records them.
A `restricted` network runs its egress proxy with the candidate image's own `python3`; an image without it is refused before launch with `restricted_network_requires_python3`.

Each run retains its workspace, snapshots, stopped final workspace, grading-source decision, selected definition and plugin artifacts, sanitized observations, and independent grades under `runs/karn/<run-id>/` by default.
The immutable schema 2 record lives under `private-results/results/<candidate-hash>/<run-id>/`.
Estimated cost is API-equivalent USD, not the subscription bill.
`cost_breakdown` beside it tallies tokens and USD by type: uncached input, cache reads, cache writes, 1-hour cache writes (Anthropic prices them above the 5-minute ones), and output.
Every cost is a standard-tier equivalent, whatever tier served the request: each priced request carries `rate_basis: "standard"`, Claude requests keep their transcript `speed` and `service_tier`, and Codex requests keep `requested_service_tier`, the tier Codex put in its request (`mixed` when a thread used several). Codex never reports the tier the server applied, so a flex trial shows up in token usage and the cost breakdown, not in the price.
Agent turns count model responses plus tool calls; missing measurements remain null with an explanation.
Turns, usage, and cost are complete only for a Codex version whose journal and telemetry were qualified against scripted ground truth (0.153.4 and 0.157.1); qualify another offline, without credentials, with `scripts/qualify_codex_telemetry.py --image IMAGE --native-version VERSION --output DIR`.
Claude Code runs are read from its session transcripts, subagents included, with the OTel stream as a cross-check; a compaction's own request appears only in OTel.
Each OTel request is reconciled with its transcript response on uncached, cache-read, cache-write, and output tokens and on the model; a disagreement or a missing field keeps the transcript's values and marks the measurements partial (`otel_usage_conflicts_with_native`, `otel_model_conflicts_with_native`, or a `…_comparison_unavailable` reason); two transcript responses claiming one request id are flagged `native_request_identity_reused`, and repeated OTel reports of one request count once, flagged `otel_request_observations_conflict` if they disagree in tokens, model, speed, query source, or cost.
Claude Code 2.1.284 is qualified, from smoke run 93ffaa74 on `bare-claude-haiku`; measurements from any other version are marked partial with `native_version_not_qualified`.
Qualify a version from a real run whose relay was on: `scripts/qualify_claude_telemetry.py runs/karn/RUN_ID --out proof.json` checks that both streams agree request by request, and rejects every disagreement the runtime reconciliation flags; it exits nonzero unless the run qualifies; commit a qualifying proof with that run's `observations.events.jsonl` under `tests/fixtures/karn_observations_claude_<version>/` and add the version to `QUALIFIED_CLAUDE_VERSIONS`.
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
  A retained record is never rewritten.
- A stopped record, one whose workspace writers were confirmed stopped, is final: recovery only publishes it if it is not published yet.
- An unconfirmed record, one with `workspace_stopped: false`, stays the run's original observation whether or not it was published.
  Recovery stops the workload, settles the run's own login, and grades once, all before it needs the results lock.
  It then retains a single linked recovery under its own stable id, with `recovery_of` and `execution_run_id` naming the original run, and publishes the original unchanged before the linked recovery.
  If either publication is blocked, or recovery is interrupted anywhere after the linked recovery is retained, the next `recover` or scheduler pass publishes whichever of the two is still unpublished, with the same ids and without grading again.
  An interruption before the linked recovery is retained leaves nothing to reuse, so the next recovery grades again.
- Authentication is settled separately from the record.
  A run whose login harvest failed (`login_harvest_failed` or `login_harvest_pending` in its execution) still owns the profile's pending login after its record is written.
  Before `recover` returns any stopped record, it checks whether this run owns the pending login and, if so, settles it under the login lock with the exact plugin artifact retained in the run directory, preserving the run's native sessions into its own evidence first.
- Recovery never settles or harvests another run's pending login: that run's container may still be live, and its native state belongs to that run's own evidence.
  Recovering that run, or the login's next run, settles it.
- Settlement never blocks publication.
  If it fails for any reason, a busy login included, the record is still published and the pending login is kept; `recover` prints the final record and exits non-zero with `login_settlement_pending:<reason>`.
  Run `recover` again once the cause is fixed.
- In a batch, a recovered row takes its execution status and recovery linkage (`recovery_record`, `recovery_of`, `execution_run_id`) from the linked recovery as soon as it is retained, even while publication is still blocked, and is marked `record_write_pending` or `login_settlement_pending` until a later scheduler pass finishes publication or settlement.
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
