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
SilverquiLLM runs a completed Karn build by itself; it needs no Ozolith package.

Build the bare Codex example and the grader image explicitly before running:

```bash
karn build examples/karn --worktree --out /tmp/bench-codex-build
silverquillm grader build
silverquillm login --build-output /tmp/bench-codex-build --construct bare-codex
silverquillm run --build-output /tmp/bench-codex-build --construct bare-codex --benchmark smoke --results-repo ./private-results
silverquillm run --build-output /tmp/bench-codex-build --construct bare-codex --benchmark hob-medium --results-repo ./private-results
```

Grading runs the agent's code only inside the grader container: no network, no access to your home directory, environment, or login.

The example selects `gpt-6-astra` and the existing Codex login plugin, with no custom skills or polling controller.
Each run records available grades, API-equivalent estimated cost, model responses, tool calls, and observation completeness.
Failed and interrupted runs remain useful data; collection has no leaderboard eligibility gate.

See [Karn benchmarking](docs/KARN-BENCHMARKING.md) for batches, recovery, retained artifacts, and historical commands.

---

## CLI Commands

| Command | Purpose |
| --- | --- |
| `silverquillm run --build-output … --construct … --benchmark …` | Execute a prebuilt Karn construct, grade its work in the grader container, and retain implementation and efficiency observations. |
| `silverquillm scheduler [--once] [--replay-without-state ID]` | Execute due Karn batches in `batches/*.toml` through the same run lifecycle. |
| `silverquillm recover RUN_ID [--stop]` | Settle an interrupted or killed run from its retained evidence and write its record, without rerunning work. |
| `silverquillm queue ls [--json]` | One-shot, read-only view of the batch queue, including interrupted, partially observed, and unsupported batches. |
| `silverquillm top` | Live, read-only view of the batch queue (`q` quits). |
| `silverquillm login --build-output … --construct …` | Enroll the construct's own subscription login through its login plugin. |
| `silverquillm grader build` | Build the pinned, network-less grader image that runs every grading pass. |
| `silverquillm results-init PATH` | Lay out an empty private results repository. |
| `silverquillm validate …` | Validate 17lands replays against the engine. |
| `silverquillm legacy run-image\|smoke\|resume\|chain\|rescore\|logs …` | The historical `--image` entrypoint lineage and its run directories. |

A `--cards` filter is available for development and pipeline validation, but filtered runs are **not** leaderboard-valid.

---

## Batches

A batch is a `batches/<id>.toml` file with `format = "karn-v4"` and ordered `[[runs]]` of build output, construct, and benchmark.
The scheduler runs batches serially and commits progress to `batches/state/<id>.json`; see [batches/README.md](batches/README.md) and [Karn benchmarking](docs/KARN-BENCHMARKING.md).
Historical Candidate Bundle batches are shown as unsupported and never run.

---

## Scoring & Leaderboards

A leaderboard-valid run requires the full target set, an unfiltered run, and a successful, evaluatable final state. Smoke runs, filtered runs, and runs that produced no viable output are excluded. The regression dimensions are reported separately rather than folded into a single composite score.

---

## Agent Images

New agents are Karn constructs: a v4 Construct Definition built into an exact image by `karn build`, which SilverquiLLM runs without rebuilding (see [Karn benchmarking](docs/KARN-BENCHMARKING.md)).
The images under [docker/](docker/) belong to the historical `--image` lineage run by `silverquillm legacy`.

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

```bash
pip install -e ".[dev]"
pytest tests/
```

Docker-backed tests are marked `integration` and deselected by default; run them with `pytest -m integration` after `silverquillm grader build`.
