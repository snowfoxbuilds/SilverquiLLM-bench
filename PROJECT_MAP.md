# Project Map — SilverquiLLM-bench

## Overview

SilverquiLLM-bench is a **Magic: The Gathering card-implementation benchmark** for evaluating LLM coding agents. Agents implement cards from a new MTG set as Python classes inside a custom Python game engine.

The project has three major parts:

1. **Game engine** — A Python port inspired by XMage, with core MTG rules systems and FDN card implementations.
2. **Benchmark runner** — A Docker-container-based orchestration harness that stages a Workspace, runs one black-box agent container, snapshots progress, harvests `workspace_final/`, and evaluates outputs.
3. **Replay validation** — A 17lands GRE replay pipeline for validating engine behavior against real MTG Arena game state streams.

The benchmark architecture now treats the **Workspace** as the only evaluatable state. Agents modify files in `/workspace/` directly, including `/workspace/engine/` and `cards/sos/{card_id}/card_impl.py`. The runner snapshots the full Workspace every 60 seconds, materializes the official evaluation state as `docker/<image_dir>/results/<run_name>/workspace_final/`, and evaluates from that directory.

## Current Canonical Architecture

```

Host runner

├── stages Workspace (copytree of benchmarks/sos/workspace/)

├── writes /workspace/run_manifest.json immediately before launch

├── launches Docker Agent Container

├── streams + saves Docker stdout/stderr directly to run_dir

├── snapshots full Workspace every 60s as host-side Git commits

├── materializes workspace_final/

├── optionally falls back to a viable snapshot if final engine is corrupted

└── evaluates from workspace_final/

Agent Container

├── receives /workspace/ and /output/ mounts

├── edits /workspace/engine/ in place

├── edits cards/sos/{card_id}/card_[impl.py](http://impl.py)

├── may write cards/sos/{card_id}/[tests.py](http://tests.py) in Tested Mode

└── may write optional telemetry to /output/

```

## Architecture Diagram

```

┌──────────────────────────────────────────────────────────────────────┐

│                         Host Benchmark Runner                        │

│                                                                      │

│  silverquillm/[cli.py](http://cli.py)                                                 │

│    ├── run                                                           │

│    └── smoke                                                         │

│                                                                      │

│  silverquillm/[workspace.py](http://workspace.py)                                           │
│    └── stage_workspace() — copytree of benchmarks/sos/workspace/     │

│                                                                      │

│  docker/<image_dir>/results/<run_name>/                              │

│    ├── workspace_final/        # official evaluation Workspace        │

│    ├── snapshots/              # host-side Git snapshot repo          │

│    ├── snapshot_telemetry.jsonl                                      │

│    ├── docker_stdout.log                                             │

│    ├── docker_stderr.log                                             │

│    ├── engine_diff.patch                                             │

│    └── run_summary.json                                              │

│                                                                      │

│  Evaluation                                                          │

│    ├── SOS Card Correctness                                          │

│    ├── FDN Card Regression                                           │

│    └── Engine Regression                                             │

└──────────────────────────────────────────────────────────────────────┘

│

│ docker run

▼

┌──────────────────────────────────────────────────────────────────────┐

│                         Agent Container                              │

│                                                                      │

│  Docker image is the full agent config                               │

│    ├── agent CLI                                                     │

│    ├── mode: blind / tested                                          │

│    ├── strategy variant                                              │

│    ├── model config                                                  │

│    └── entrypoint behavior                                           │

│                                                                      │

│  /workspace/                                                         │

│    ├── [prompt.md](http://prompt.md)                                                     │

│    ├── run_manifest.json                                             │

│    ├── engine/                 # agent edits in place                 │

│    ├── cards/fdn/              # filled FDN examples                  │

│    └── cards/sos/              # SOS targets                          │

│                                                                      │

│  /output/                                                            │
│    └── optional telemetry only                                       │
│        system.log, agent_stdout.log, etc.                            │

└──────────────────────────────────────────────────────────────────────┘


## Directory Structure

| Directory | Status | Purpose | Notes |
|---|---:|---|---|
| `benchmarks/sos/workspace/engine/` | Active | Core MTG game engine | Canonical location; agent edits staged copy in `/workspace/engine/` during runs |
| `benchmarks/sos/workspace/cards/` | Active | Card registry and set data | Registry, Scryfall helpers, FDN/SOS card directories |
| `benchmarks/sos/workspace/cards/fdn/` | Active | FDN per-card implementations | 276 card directories with 286 `card_impl.py` files; 174 cards implemented/upgraded in Items 1–15 |
| `benchmarks/sos/workspace/cards/sos/` | Active | SOS benchmark targets | Empty/template impls before agent run; agent fills `card_impl.py` |
| `benchmarks/sos/workspace/tests/` | Active | Workspace-internal tests | Engine unit tests, test_utils.py, conftest.py |
| `silverquillm/` | Active | Benchmark runner package | CLI, workspace staging, evaluation, telemetry, live viewer, results |
| `silverquillm/replay/` | Active | 17lands replay validation pipeline | Parser, state reconstruction, executor, divergence reporting |
| `docker/` | Active | Agent container images | Image is the full agent config |
| `docker/homelab-pi-blind/` | Active | Pi blind-mode image (homelab) | Agent-specific entrypoint and model config |
| `docker/local-pi-blind/` | Active | Pi blind-mode image (local) | Agent-specific entrypoint and model config |
| `docker/copilot-gpt-4.1/` | Active | Copilot GPT-4.1 image | Agent-specific entrypoint |
| `docker/copilot-gpt-5.4/` | Active | Copilot GPT-5.4 image | Agent-specific entrypoint |
| `docker/copilot-gpt-5.4-mini/` | Active | Copilot GPT-5.4-mini image | Agent-specific entrypoint |
| `docker/copilot-local/` | Active | Copilot local image | Agent-specific entrypoint |
| `benchmarks/` | Active | Benchmark data sets | SOS data and benchmark set metadata |
| `benchmarks/sos/` | Active | SOS Draft Set data | 346-card benchmark set |
| `benchmarks/sos/workspace/` | Active | **Canonical agent workspace** | Copied as-is to Docker mount; contains engine, cards, tests, rulebook |
| `benchmarks/sos/data/` | Active | SOS raw data + audited tests | sos.json, rules, tests/audited/ |
| `data/` | Active | Runtime data cache + replay data | Scryfall cache, replay files |
| `data/replays/` | Active | Replay card ID maps and samples | Used by replay validation |
| `scripts/` | Active | Utility scripts | Card ID maps, card spec generation, migration scripts |
| `tests/` | Active | Test root | Runner, card, replay, integration, and host-side validation tests |
| `tests/integration/` | Active | Integration tests | Workspace staging integration tests |
| `docs/` | Active | Specs and generated docs | Export target for Notion specs |

## Key Specs

| Spec | Purpose |
|---|---|
| `PROJECT-OVERVIEW.md` | Project goals, scope, phases, benchmark motivation |
| `GAME-ENGINE.md` | Engine architecture, XMage porting strategy, core rules systems |
| `CARD-INTERFACE.md` | Card class contract, hooks, modes, replacement effects |
| `TEST-SUITE.md` | Audited tests, test harvester, FDN/SOS test structure |
| `BENCHMARK-RUNNER.md` | Host-side runner overview |
| `AGENT-CONTAINERS.md` | Docker Agent Container architecture |
| `WORKSPACE-CONTRACT.md` | Canonical Workspace layout and card/engine edit contract |
| `RUN-ARTIFACTS-AND-TELEMETRY.md` | `workspace_final/`, Git snapshots, telemetry, fallback, Docker logs |
| `SCORING.md` | Three evaluation dimensions and leaderboard format |
| `TESTING-CONVENTIONS.md` | Test safety rules and pytest conventions |
| `17LANDS-REPLAY-SCHEMA.md` | GRE replay JSON schema and parsing strategy |


## Key Runtime Patterns

- **Image-as-config**: Docker image encodes agent, mode, strategy, model, and prompt behavior.
- **Workspace-as-output**: The Workspace is the only evaluatable output state.
- **Workspace copytree**: `stage_workspace()` copies `benchmarks/sos/workspace/` as-is, then applies per-run overlays.
- **In-place engine editing**: Agents modify `/workspace/engine/` directly.
- **Host baseline engine**: Runner computes `engine_diff.patch` against the original host engine.
- **Snapshot fallback**: Runner can recover from corrupted final engine state using whole-Workspace Git snapshots.
- **Telemetry-only output**: `/output/` and Docker logs are for monitoring/debugging only. No progress.jsonl channel.
- **Direct docker log streaming**: Docker stdout/stderr are streamed line-by-line directly to run_dir during container execution.
- **Evaluation from `workspace_final/`**: Evaluation never depends on `/output/`.
- **Card structure invariant**: Each card class must remain in `cards/{set}/{card_id}/card_impl.py`.
- **Filtered runs are not leaderboard-valid**: `--cards` is for development and pipeline validation only.
- **Smoke runs are not benchmark runs**: `silverquillm smoke` validates containers with a tiny synthetic Workspace.

## Engine Patterns

- **DeterministicPlayer**: Tests use scripted player choices for reproducibility.
- **Identity-based zone lookups**: Zone operations use object identity rather than equality.
- **Centralized zone transitions**: `move_to_zone()` handles replacement effects, events, and trigger registration.
- **Event-driven triggers**: Trigger registration/unregistration follows permanent lifecycle.
- **Replacement effects**: Applied before events mutate state.
- **Layer system**: Continuous effects reset to base characteristics and reapply in layer order.
- **Protection DEBT integration**: Damage, Enchanting/Equipping, Blocking, Targeting checks integrated at mechanic points.
- **Hybrid mana**: Uses `HybridManaSymbol` and payment solver logic.
- **Converge**: Mana colors spent are tracked during casting.
- **Extra turns**: Extra turns are inserted without advancing normal rotation.

## Testing

- **Framework**: pytest
- **Global safety**: `pytest-timeout` default protects against hanging tests.
- **Test safety rules**:
  - No real `os.kill*()` or signal calls in unit tests.
  - Explicit fake PIDs for mocks.
  - No infinite loops or long sleeps.
  - No open-ended `game.run()` in unit tests.
  - Mock subprocesses in unit tests.
- **Engine tests**: `tests/engine/`
- **FDN audited tests**: `tests/audited/fdn/`
- **SOS audited tests**: `tests/audited/sos/`
- **Integration tests**: Docker/model smoke tests should be marked `@pytest.mark.integration`.

## Build and Config

- **Python**: ≥3.12
- **Build**: setuptools via `pyproject.toml`
- **CLI**: `silverquillm`
- **Docker**: Agent images in `docker/`; runner uses Docker CLI via subprocess.
- **Colorized logs**:
  - `--color auto` default
  - `--color always`
  - `--color never`
- **Run Manifest**: Written by runner immediately before container launch.
- **No benchmark `config.yaml`**: Docker image is the agent configuration.

## Migration Notes

### FDN migration (COMPLETE)

FDN card implementations have been fully migrated to per-card directories:

```
cards/fdn/{card_id}/
  card_spec.json
  card_impl.py
```

276 card directories with 286 `card_impl.py` files. 174 cards were newly implemented or upgraded to full oracle text across Items 1–15, covering all colors (White, Blue, Black, Red, Green), multicolor, artifacts, equipment, planeswalkers, and lands.

### Runner migration

Required changes from older runner state:

- Remove `engine_work/`.
- Write `run_manifest.json` before Docker launch.
- Enforce hard timeout with `Popen` + explicit `docker stop -t 10`.
- Capture Docker stdout/stderr live and to files.
- Add `workspace_final/`.
- Add 60-second Git Workspace snapshots.
- Add `snapshot_telemetry.jsonl`.
- Evaluate from `workspace_final/`.
- Treat `/output/` as optional telemetry only.