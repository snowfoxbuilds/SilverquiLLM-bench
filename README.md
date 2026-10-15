# SilverquiLLM-bench

Latest results live on [snowfoxbuilds.com](https://snowfoxbuilds.com/silverquillm), and the newest round is written up in [the hob-medium Post](https://snowfoxbuilds.com/blog/silverquillm-hob-medium/). To hear about each new write-up when it comes out, subscribe to [the newsletter](https://snowfoxbuilds.substack.com).

A benchmark for evaluating LLM coding agents by tasking them with implementing **Magic: The Gathering** cards as Python classes inside a custom game engine.

Each task is a small but real software-engineering job: read a spec, understand natural-language rules text, extend an existing codebase, and produce a working, tested implementation. Cards are drawn from a recently released MTG set to minimize training-data contamination and measure genuine code-generation ability rather than recall.

---

## What This Benchmark Measures

SilverquiLLM-bench is designed to evaluate coding agents the way you'd evaluate a software contributor — by the quality of the code they ship, not by multiple-choice answers.

- **Agent- and model-independent.** Agents run as black-box Docker containers. A Karn candidate pairs a prebuilt immutable image with its complete Construct Definition (Karn v5, or an earlier v4 build). The benchmark supplies task data, a fresh workspace, an execution budget, and the selected local login.
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

Runs currently need [Karn](https://snowfoxbuilds.com/karn) to build the agent images, and Karn isn't public yet. Until it is, the engine, the tests and the benchmark data are all here to read.

Use Python 3.13, Docker, Karn on the build host, and a host Codex or Claude Code CLI for subscription enrollment.
Install the benchmark with `pip install -e .`.
SilverquiLLM-bench runs a completed Karn build by itself; it needs no Ozolith package.

The candidate recipes live in the results repository at `karn/constructs/<label>`. Build them from its committed tree, then build the grader image, before running.
Commands find the results repository, batch queue, run directory, login state and this checkout through their flags or `~/.config/silverquillm/config.toml` (see [Karn benchmarking](docs/KARN-BENCHMARKING.md#host-configuration)).
The operator runbook — how to queue, monitor, publish, re-score and analyse — lives in the results repository's `AGENTS.md`, and operational agents work from that checkout:

```bash
mkdir -p ~/.config/silverquillm
printf 'results_repo = "~/bench-results"\nbench_root = "~/SilverquiLLM-bench"\nbatches_dir = "~/raw-bench-results/batches"\nruns_dir = "~/raw-bench-results/runs"\n' > ~/.config/silverquillm/config.toml
karn build ~/bench-results/karn --out ~/bench-builds/roster-1
silverquillm grader build
silverquillm login --build-output ~/bench-builds/roster-1 --construct bare-codex
silverquillm run --build-output ~/bench-builds/roster-1 --construct bare-codex --benchmark smoke
silverquillm run --build-output ~/bench-builds/roster-1 --construct bare-codex --benchmark hob-medium
```

Grading runs the agent's code only inside the grader container: no network, no access to your home directory, environment, or login.

The roster runs GPT-6 Astra, Sol and Luna on Codex with a ChatGPT subscription, and Claude Opus 5.5, Sonnet 5.5, Fable 5.1 and Haiku 4.5 on Claude Code with a Claude subscription, each through Karn's login plugin for its CLI.
Each run records available grades, API-equivalent estimated cost with its per-type breakdown, model responses, tool calls, and observation completeness.
Failed and interrupted runs remain useful data; collection has no leaderboard eligibility gate.

See [Karn benchmarking](docs/KARN-BENCHMARKING.md) for batches, recovery, retained artifacts, and historical commands.

---

## CLI Commands

| Command | Purpose |
| --- | --- |
| `silverquillm run --build-output … --construct … --benchmark …` | Execute a prebuilt Karn construct, grade its work in the grader container, and retain implementation and efficiency observations. |
| `silverquillm scheduler [--once] [--replay-without-state ID]` | Execute due Karn batches in the batch directory, in queue order, through the same run lifecycle. |
| `silverquillm recover RUN_ID [--stop]` | Settle an interrupted or killed run from its retained evidence and write its record, without rerunning work. |
| `silverquillm regrade --benchmark … --out DIR [--run ID] [--candidate HASH]` | Re-grade retained runs on the current Audited Tests and grading inputs, writing new scores to DIR; records are never changed. |
| `silverquillm queue ls [--json]` | One-shot, read-only view of the batch queue, including interrupted, partially observed, and unsupported batches. |
| `silverquillm queue pause\|drain\|resume` | Stop launching new runs (drain also stops the scheduler once nothing is in flight), or launch again; runs in flight are never interrupted. |
| `silverquillm top` | Read-only monitor: live runs, the queue, Login Profiles with Estimated Weekly Usage, history, and run details with live output (`q` quits; needs the `monitor` extra). `--json` prints one snapshot for scripts and agents without a terminal. |
| `silverquillm login --build-output … --construct …` | Enroll the construct's own subscription login through its login plugin. |
| `silverquillm grader build [--python X.Y]` | Build the pinned, network-less grader images, one per graded Python version; each run is graded on its candidate's version. |
| `silverquillm results-init PATH` | Lay out an empty private results repository and, if none exists, a minimal host configuration. |
| `silverquillm grading-inputs BENCHMARK` | Print a benchmark's current grading-inputs digest as JSON. |
| `silverquillm validate …` | Validate 17lands replays against the engine. |
| `silverquillm data fetch-hob-set\|fetch-fra-set\|card-id-map\|token-id-map\|download-replays` | Fetch and build the reference data under `data/`. |
| `silverquillm build fra-hard\|port-from-known-best\|printed-classes\|fdn-specs\|audited-stubs` | Generate benchmark inputs. |
| `silverquillm audit check-promotion\|printed-identity` | Gate a candidate Audited Test for promotion; rewrite name-string card identification in tests. |
| `silverquillm qualify claude-telemetry\|codex-telemetry` | Qualify an agent CLI version's telemetry before its accounting is trusted. |
| `silverquillm legacy run-image\|smoke\|resume\|chain\|rescore\|logs …` | The historical `--image` entrypoint lineage and its run directories. |

A `--cards` filter is available for development and pipeline validation, but filtered runs are **not** leaderboard-valid.

---

## Batches

A batch is a `batches/<id>.toml` file with `format = "karn-v5"` (earlier `karn-v4` files still run) and ordered `[[runs]]` of build output, construct, and benchmark.
The scheduler fills free login slots across batches in queue order, picks up a batch added while it runs, and keeps its progress in the batch directory's `state/<id>.json`; see [batches/README.md](batches/README.md) and [Karn benchmarking](docs/KARN-BENCHMARKING.md).
Historical Candidate Bundle batches are shown as unsupported and never run.

---

## Scoring & Leaderboards

A leaderboard-valid run requires the full target set, an unfiltered run, and a successful, evaluatable final state. Smoke runs, filtered runs, and runs that produced no viable output are excluded. The regression dimensions are reported separately rather than folded into a single composite score.

Published results are on [snowfoxbuilds.com](https://snowfoxbuilds.com/silverquillm).

---

## Agent Images

New agents are Karn constructs: a v5 Construct Definition built into an exact image by `karn build`, which SilverquiLLM-bench runs without rebuilding (see [Karn benchmarking](docs/KARN-BENCHMARKING.md)).
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
pytest tests/ -n auto
```

`-n auto` runs the suite in parallel with pytest-xdist; leave it off to run serially.

Docker-backed tests are marked `integration` and deselected by default; run them with `pytest -m integration` after `silverquillm grader build`.
