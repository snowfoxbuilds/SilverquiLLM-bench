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
# A Candidate Bundle through TheOzolith's Run Contract (the current contract):
silverquillm run --candidate candidates/vanilla-claude--4e8b75b6 --benchmark smoke --timeout 3600
# The legacy entrypoint lineage (being phased out):
silverquillm run --image my-agent:latest --timeout 7200
```

A **Candidate Bundle** (`candidates/README.md`) is the only input of a
Contract Run: the bench verifies it through TheOzolith's verifier, recomputes
its identity (never trusted from a recorded value), builds its derived image
through the verified standalone build, launches it by image ID with the
in-image harness as PID 1, and records the run under the recomputed identity.
The bundle's `secret_slots` name the environment variables the bench binds
(`ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` for claude, `CODEX_AUTH_JSON`
for codex). The current vanilla reference candidates ship under `candidates/`;
they are examples, not a closed set — a further candidate is one more exported
directory, with no adapter or model registry to update.

---

## CLI Commands

| Command | Purpose |
| --- | --- |
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

The bench-side lifecycle of a candidate (`docs/specs/BENCHMARK-CANDIDATES.md`):

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
   time). A run whose candidate is not checked in under `candidates/` (or does
   not verify) is refused outright; a run with `leaderboard_valid: false` is a
   warning, publishable with `--allow-invalid` and filtered out of any
   leaderboard mechanically. Review the diff and commit.

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
