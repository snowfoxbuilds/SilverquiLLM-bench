# SilverquiLLM-bench

A benchmark for evaluating LLM coding agents by tasking them with implementing **Magic: The Gathering** cards as Python classes inside a custom game engine.

Each task is a small but real software-engineering job: read a spec, understand natural-language rules text, extend an existing codebase, and produce a working, tested implementation. Cards are drawn from a recently released MTG set to minimize training-data contamination and measure genuine code-generation ability rather than recall.

---

## What This Benchmark Measures

SilverquiLLM-bench is designed to evaluate coding agents the way you'd evaluate a software contributor — by the quality of the code they ship, not by multiple-choice answers.

- **Agent- and model-independent.** Agents run as black-box Docker containers. The image *is* the entire agent configuration — CLI, model, prompt, and strategy. The harness only supplies a workspace, API keys, and a timeout, so any agent that can edit files in a container can be benchmarked on equal footing: Claude Code, Copilot, custom harnesses, multi-pass reviewers, and more.
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

The current target set is **Secrets of Strixhaven (SOS)**, a recently released MTG set. The **Foundations (FDN)** set is fully implemented and ships alongside the targets as in-context **reference examples**, so agents can learn the engine's idioms before implementing new cards.

> **The exact cards used for benchmarking are subject to change.** The benchmark currently runs against a small subset (**10 SOS cards**) while the suite is tuned; this selection — and its size — will evolve over time. Treat the active card set as a moving target, not a fixed contract.

---

## How It Works

```
Stage Workspace → Run Agent Container → Snapshot progress → Harvest final state → Evaluate
```

1. **Stage** — the harness builds a fresh workspace containing the engine source, reference cards, target templates, a rulebook, and the task prompt.
2. **Run** — it launches a single agent container, which edits the engine and target card implementations in place.
3. **Snapshot** — the full workspace is periodically committed to a host-side snapshot history for progress telemetry and recovery from a corrupted final state.
4. **Harvest** — the final workspace is materialized as the official, immutable evaluation state.
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

### Prerequisites

- Python ≥ 3.12
- Docker
- An agent image (see [Agent Images](#agent-images))

### Install

```bash
git clone https://github.com/snowfoxbuilds/SilverquiLLM-bench.git
cd SilverquiLLM-bench
pip install -e ".[dev]"
```

This installs the `silverquillm` CLI (also aliased as `benchmark`). API keys are read from the environment or a repo-root `.env` and passed through to the container.

### Build and smoke-test an image

```bash
docker build -t my-agent:latest docker/my-agent/
silverquillm smoke --image my-agent:latest
```

Smoke runs validate that a container starts and produces output — they use a tiny synthetic task and never enter benchmark results.

### Run a benchmark

```bash
# An explicit standalone Karn Construct Definition:
silverquillm run --candidate definition.json --benchmark smoke --timeout 3600
# The historical entrypoint lineage:
silverquillm run --image my-agent:latest --timeout 7200
```

A candidate pairs a versioned runtime definition with an immutable image already available in your local Docker Engine.
The benchmark validates the declaration, selects the actual image ID, supplies the declared files and runs the configured process.
Neither an Ozolith installation nor a Node Daemon is required.
With a non-editable wheel installation, set `SILVERQUILLM_BENCH_ROOT` to this benchmark data checkout; it supplies the prompts, workspaces and audited suites.
Basic and planned prompts, proposal validation, isolated gates and audited grading belong to the benchmark.
Distinct definitions can share one image while receiving different candidate identities.

The current host supports Docker Automatons with launch-private runtime mounts, configured initialization/bootstrap and direct raw credentials.
Bind sources, persistent mounts, host plugins, retained login lifecycle and relay/provider credentials are explicitly unsupported and refused before launch.
See [Bench Contract](docs/specs/BENCH-CONTRACT.md) for the exact capability boundary and raw-secret binding convention.
Historical bundles and results keep their original meaning; new runs require explicit definitions.

---

## CLI Commands

| Command | Purpose |
| --- | --- |
| `silverquillm run --candidate <definition> --benchmark … [--mode basic\|planned] [--results-repo …]` | Run a standalone definition using the existing immutable image, declared file interface, isolated gates and audited grading; record definition and image identity. |
| `silverquillm run --image … --timeout …` | Launch a legacy entrypoint-lineage run (being phased out). |
| `silverquillm smoke --image …` | Validate that an image starts and produces output. |
| `silverquillm resume <run_id> --timeout …` | Continue from a prior run's final state as an independent leg. |
| `silverquillm chain <run_id>` | Print the chain of resume legs leading to a run. |
| `silverquillm rescore <run_id>` | Re-run audited tests against an existing run and rewrite its scores. |
| `silverquillm logs --run <run_name>` | Tabbed, per-channel log viewer (live or archived). |
| `silverquillm scheduler [--once] [--replay-without-state ID] [--acknowledge-cleanup ID]` | Run the single-writer batch scheduler over `batches/*.toml` (serial, name order then file order, `not_before` respected, identity resolved at run start; committed portable state in `batches/state/`; a batch without state is blocked until acknowledged; abandoned containers reconciled before anything runs). |
| `silverquillm queue ls` | One-shot, read-only table of the batch queue: batches, `not_before`, per-run specs and states, and every blocked batch (missing state, unreadable state, an abandoned run). |
| `silverquillm top` | Live, read-only view of the queue (`q` quits). |
| `scripts/promote_candidate.py <definition.json>` | Promote an explicit definition into `candidates/` (vendor-at-promote is strict; the whole tree is scanned for secret values; never runs git). |
| `scripts/publish_results.py --results-repo … --dest published/<subdir> RUN_ID…` | Publish Run Records into `published/` transactionally (traceability = hard refusal, validity = warning; never commits). |

A `--cards` filter is available for development and pipeline validation, but filtered runs are **not** leaderboard-valid.

---

## Candidates, Batches, and Publishing

The bench-side lifecycle of a candidate (`docs/specs/BENCHMARK-CANDIDATES.md`):

1. **Promote.** `python scripts/promote_candidate.py definition.json` writes
   `candidates/<slug>--<hash8>/` with the canonical definition, exact source
   copy, hashed source inventory and README. It verifies the whole tree for
   credential values before atomic publication. The source proves the
   definition; it does not attest an image build. Review and commit it yourself.
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
