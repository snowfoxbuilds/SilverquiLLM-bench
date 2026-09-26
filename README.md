# SilverquiLLM-bench

A benchmark for evaluating LLM coding agents by tasking them with implementing **Magic: The Gathering** cards as Python classes inside a custom game engine.

Each task is a small but real software-engineering job: read a spec, understand natural-language rules text, extend an existing codebase, and produce a working, tested implementation. Cards are drawn from a recently released MTG set to minimize training-data contamination and measure genuine code-generation ability rather than recall.

---

## What This Benchmark Measures

SilverquiLLM-bench is designed to evaluate coding agents the way you'd evaluate a software contributor — by the quality of the code they ship, not by multiple-choice answers.

- **Agent- and model-independent.** Agents run as black-box Docker containers. A Karn candidate pairs a prebuilt immutable image with its complete v4 Construct Definition. The benchmark supplies task data, a fresh workspace, an execution budget, and the selected local login.
- **Full isolation.** Every run gets a fresh workspace in its own container. There is no shared state between runs, no network dependence on the grader, and no cross-agent leakage.
- **Low contamination risk.** Targets come from a newly released MTG set that did not exist at training time, and the hidden test suite is never mounted into the container. Agents are scored on code they actually wrote against tasks they could not have memorized.
- **Mimics a full engineering workflow.** Agents don't emit a single answer — they explore a real codebase, study reference implementations, extend a shared engine, and (optionally) write their own tests. Success requires reusable design and not breaking existing behavior, exactly like contributing to a live project.

---

## Why MTG Cards?

Magic cards make good coding-benchmark tasks because they:

- **Span a wide difficulty range** — from vanilla creatures to cards with many interacting abilities.
- **Translate natural language into code** — rules text must become executable behavior.
- **Reward good architecture** — agents often need reusable engine extensions, not one-off hacks.
- **Have clear correctness signals** — card behavior is testable with deterministic game states.
- **Resist memorization** — new sets introduce new mechanics and fresh card text.

---

## Benchmark Set

The current integration workstream focuses on **hob-medium**, its five selected Hobbit cards, and its independent oracle. Historical SOS benchmarks remain available. The shipped **Foundations (FDN)** implementations provide in-context **reference examples**. The [coverage ledger](benchmarks/hob-medium/data/fdn_regression_coverage.json) records tested behavior and known baseline limitations.

> Each benchmark's `config.json` identifies its selected cards. `hob-medium` selects five HOB cards; historical SOS runs select ten SOS cards. Test coverage is reported with each run.

---

## How It Works

```
Stage Workspace → Run Agent Container → Snapshot progress → Harvest final state → Evaluate
```

1. **Stage** — the harness builds a fresh workspace containing the engine source, reference cards, target templates, a rulebook, and the task prompt.
2. **Run** — it launches a single agent container, which edits the engine and target card implementations in place.
3. **Snapshot** — the runner retains workspace-only copies for recovery from an unusable final engine.
4. **Harvest** — the final workspace is preserved. If its engine cannot load, a proven usable snapshot can supply grading; the record names both states and the fallback reason.
5. **Evaluate** — scoring runs post-hoc against the harvested workspace using a hidden, audited test suite.

---

## Evaluation Dimensions

Three independent dimensions are scored against the agent's harvested engine:

| Dimension | What it measures |
| --- | --- |
| **Card Correctness** | Whether the agent's target card implementations pass audited tests |
| **Reference Regression** | Whether the agent's engine changes broke the pre-filled reference cards |
| **Engine Regression** | Whether the agent's engine changes broke core game mechanics |

Audited tests are never visible to the agent. Agent-written tests are harvested as artifacts but are not scored.

---

## Quickstart

Use Python 3.13, Docker, Karn on the build host, and a host Codex CLI for subscription enrollment.
Install the benchmark with `pip install -e .`.
The benchmark package runs independently of Ozolith's daemon and builder packages.

Build the bare Codex example explicitly before scheduling a run:

```bash
karn build examples/karn --worktree --out /tmp/bench-codex-build
silverquillm karn login benchmark --build-output /tmp/bench-codex-build --construct bare-codex
silverquillm karn run --build-output /tmp/bench-codex-build --construct bare-codex --benchmark smoke --login benchmark --results-repo ./private-results
silverquillm karn run --build-output /tmp/bench-codex-build --construct bare-codex --benchmark hob-medium --login benchmark --results-repo ./private-results
```

The example selects `gpt-6-astra` and the existing Codex login plugin, with no custom skills or polling controller.
Each run records available grades, API-equivalent estimated cost, model responses, tool calls, and observation completeness.
Failed and interrupted runs remain useful data; collection has no leaderboard eligibility gate.

See [Karn benchmarking](docs/KARN-BENCHMARKING.md) for batches, recovery, retained artifacts, and historical commands.

---

## CLI Commands

| Command | Purpose |
| --- | --- |
| `silverquillm karn run --build-output … --construct … --benchmark … --login …` | Execute a prebuilt Karn candidate and retain implementation and efficiency observations. |
| `silverquillm karn scheduler --once --replay-without-state ID` | Execute due Karn batches through the same run lifecycle. |
| `silverquillm karn queue` | Inspect Karn queue state and recorded outcomes. |
| `silverquillm run --candidate <bundle> --benchmark … [--mode basic\|planned] [--results-repo …]` | Drive a Candidate Bundle through TheOzolith's implementer Run Contract: bundle verification + identity recomputation, vendored results-repo copy, verified image build, production job dir, gate over the jobs channel, post-exit proposal application, Audited Eval, RunRecord under the verified identity. |
| `silverquillm run --image … --timeout …` | Launch a legacy entrypoint-lineage run (being phased out). |
| `silverquillm smoke --image …` | Validate that an image starts and produces output. |
| `silverquillm resume <run_id> --timeout …` | Continue from a prior run's final state as an independent leg. |
| `silverquillm chain <run_id>` | Print the chain of resume legs leading to a run. |
| `silverquillm rescore <run_id>` | Re-run audited tests against an existing run and rewrite its scores. |
| `silverquillm logs --run <run_name>` | Tabbed, per-channel log viewer (live or archived). |
| `silverquillm scheduler [--once] [--replay-without-state ID] [--acknowledge-cleanup ID]` | Run the single-writer batch scheduler over `batches/*.toml` (serial, name order then file order, `not_before` respected, identity resolved at run start; committed portable state in `batches/state/`; a batch without state is blocked until acknowledged; abandoned containers reconciled before anything runs). |
| `silverquillm queue ls` | One-shot, read-only table of the batch queue: batches, `not_before`, per-run specs and states, and every blocked batch (missing state, unreadable state, an abandoned run). |
| `silverquillm top` | Live, read-only view of the queue (`q` quits). |
| `scripts/promote_candidate.py <config-repo> <worker-type>` | Promote a worker-type definition into `candidates/` (vendor-at-promote is strict; the whole tree is scanned for secret values; never runs git). |
| `scripts/publish_results.py --results-repo … --dest published/<subdir> RUN_ID…` | Publish Run Records into `published/` transactionally (traceability = hard refusal, validity = warning; never commits). |

A `--cards` filter is available for development and pipeline validation, but filtered runs are **not** leaderboard-valid.

---

## Candidates, Batches, and Publishing

The following historical Candidate Bundle commands require the optional `legacy` extra (`pip install -e ".[legacy]"`).
The existing [legacy Docker examples](docker/) remain available for those historical image workflows.
Their production proposal and publication behavior remains specific to those records.
For new runs, use [Karn benchmarking](docs/KARN-BENCHMARKING.md).

The historical bench-side lifecycle (`docs/specs/BENCHMARK-CANDIDATES.md`):

1. **Promote.** `python scripts/promote_candidate.py <config-repo> <worker-type>`
   copies a worker-type definition from your private Config Repo into
   `candidates/<slug>--<hash8>/` — definition (base pinned by digest), the
   knowledge and policy source trees it references, the exported bundle, and a
   README stub you complete. A referenced knowledge tree must carry a
   `PUBLISHABLE` marker at its root or the candidate cannot be promoted:
   knowledge that cannot be published means its results cannot be published
   either. The whole directory is scanned for secret values before it appears
   and the generated files name no host-local path; promoting the same
   identity again is a no-op only when the vendored source is unchanged (your
   completed README is never compared). Commit the directory yourself — the
   commit is the approval stamp.
2. **Queue.** Write `batches/<id>.toml` (an optional `not_before` plus ordered
   `[[runs]]` of candidate + mode + benchmark + budget; `batches/README.md`),
   start it with `silverquillm scheduler --replay-without-state <id>` (a batch
   without committed state is blocked, because starting from entry 0 could
   replay finished runs), and commit `batches/state/<id>.json` as the
   scheduler advances it. Batches execute serially; the file is re-read before
   every not-yet-started run; each candidate's identity is recomputed at run
   start; a failed run is recorded and the batch continues; a run abandoned by
   a dead scheduler has its container removed before anything else runs.
   `silverquillm queue ls` and `silverquillm top` show the queue without
   touching it. Batch ids are one-shot: never reuse one.
3. **Publish.** `python scripts/publish_results.py --results-repo <clone>
   --dest published/<subdir> RUN_ID...` publishes `manifest.json` +
   `scores.json` per run into `published/` as one transaction (all requested
   records or none; an interrupted run is recovered from its journal next
   time, and recovery removes only what that journal proves it created under
   the destination). A run whose candidate is not checked in under
   `candidates/` (or does not verify) is refused outright; a run with
   `leaderboard_valid: false` is a warning, publishable with `--allow-invalid`
   and filtered out of any leaderboard mechanically. `--dry-run` checks and
   reports without writing anything. Review the diff and commit.

---

## Scoring & Leaderboards

A leaderboard-valid run requires the full target set, an unfiltered run, and a successful, evaluatable final state. Smoke runs, filtered runs, and runs that produced no viable output are excluded. The regression dimensions are reported separately rather than folded into a single composite score.

---

## Agent Images

The Docker image bakes in the agent CLI, mode, strategy, model, and prompt — the harness supplies only volumes, API keys, and a timeout. To add an agent, create a new image directory following the existing entrypoint pattern (output capture and SIGTERM handling). Any image that can read the staged workspace and edit files in place can be benchmarked.

---

## Game Engine

A Python engine inspired by [XMage](https://github.com/magefree/mage), implementing core MTG rules for two-player games: turn structure, stack and priority, casting and resolution, combat, mana payment, zones, card types/subtypes, triggered abilities, replacement effects, continuous effects (layer system), state-based actions, protection, and extra turns. Card implementations subclass `CardImpl` or type-specific classes such as `Creature`, `Instant`, `Sorcery`, `Artifact`, `Enchantment`, `Planeswalker`, and `Land`.

---

## Replay Validation

The engine's correctness is independently validated against real game data by parsing 17lands GRE replays and comparing the engine's reconstructed game state against the recorded MTG Arena state stream at message boundaries. This is used to validate the base engine before scored benchmark runs.

---

## Contamination Controls

- **New target set** — targets did not exist at training time.
- **Container isolation** — agents see only the staged workspace.
- **Hidden tests** — audited tests are never mounted into the container.
- **No cross-run leakage** — each run gets a fresh workspace and container.
- **Reference examples are intentional** — filled reference cards are teaching material, not contamination.

---

## Acknowledgments

The game engine is inspired by [XMage](https://github.com/magefree/mage), an open-source Magic: The Gathering simulator.

## License

MIT — see [LICENSE](LICENSE) for details.

## Local development checks

The complete repository test suite includes historical Candidate Bundle tests and therefore uses both development and legacy test dependencies:

```bash
pip install -e ".[dev,legacy]"
pytest tests/
```

The Karn runtime itself has no legacy dependency requirement.
A clean wheel installation can run `silverquillm karn` and its direct/batch benchmarks independently of all Ozolith runtime and builder packages.
