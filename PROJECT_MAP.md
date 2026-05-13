# Project Map — SilverquiLLM-bench

## Overview

SilverquiLLM-bench is a **Magic: The Gathering game engine** built in Python, designed as a benchmark for evaluating LLM coding capabilities. The engine implements core MTG rules (comprehensive rules §100–§700+) for two-player games using cards from the **Foundations (FDN)** set.

The project includes a **benchmark runner package** (`silverquillm/`) that orchestrates the full evaluation pipeline: classifying cards by complexity, generating specs and prompts for LLM agents, managing Docker container execution, evaluating implementations across three dimensions (SOS card correctness, FDN regression, engine regression), scoring results, and recording artifacts. The first benchmark set is **Shadows over Sonnenthal (SOS)** with 346 cards (271 SOS base + 65 SOA Mystical Archives + 10 SPG Special Guests).

The project also includes a **replay validation pipeline** (`silverquillm/replay/`) that parses 17lands GRE replay data from real MTG Arena games and validates the engine's behavior against ground-truth game state snapshots, detecting divergences where the engine differs from the official game client.

The codebase is ~40,000+ lines across source and tests, with **~3,200+ test functions** providing thorough coverage of all engine subsystems, the benchmark pipeline, and the replay validation pipeline.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Benchmark Runner                           │
│  silverquillm/cli.py       — CLI entry point (run, smoke)        │
│  silverquillm/workspace.py — workspace isolation + volume setup  │
│  silverquillm/results.py   — per-card result collection          │
│                   │                                  │           │
│    ┌──────────────▼──────────┐      ┌────────────────▼────────┐  │
│    │    Card Pipeline        │      │    Eval Pipeline        │  │
│    │                         │      │                         │  │
│    │  card_spec.py           │      │  evaluator.py           │  │
│    │  card_loader.py         │      │  (SOS correctness,      │  │
│    │                         │      │   FDN regression,       │  │
│    │                         │      │   engine regression)    │  │
│    └─────────────────────────┘      └─────────────────────────┘  │
│                                                                  │
│    ┌──────────────────────────────────────────────────────────┐  │
│    │    Docker Containers (replace adapters)                  │  │
│    │                                                          │  │
│    │  docker/opencode-tested/  — OpenCode tested-phase image  │  │
│    │    entrypoint.sh          — card loop + progress.jsonl   │  │
│    │  docker/opencode-blind/   — OpenCode blind-phase image   │  │
│    │    entrypoint.sh          — blind impl + progress.jsonl  │  │
│    │                                                          │  │
│    │  Host runner launches containers via subprocess           │  │
│    │  (no docker Python package — uses docker CLI directly)   │  │
│    └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│    ┌──────────────────────────────────────────────────────────┐  │
│    │    Replay Validation Pipeline                            │  │
│    │    (exists but not yet wired into the new CLI)           │  │
│    │                                                          │  │
│    │  replay/types.py      — ReplayGame, GameSnapshot, etc.   │  │
│    │  replay/state.py      — GRE state reconstruction         │  │
│    │  replay/parser.py     — parse_replay() entry point       │  │
│    │  replay/executor.py   — ReplayExecutor (state-diff mode) │  │
│    │  replay/validation.py — Divergence detection & reporting │  │
│    │  replay/cli.py        — replay validation (not yet       │  │
│    │                         registered in CLI group)         │  │
│    └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                         Game Loop                                │
│  engine/game.py — create_game, run_game, helper actions          │
│  engine/turn.py — run_turn, phase/step progression               │
│                   │                                  │           │
│    ┌──────────────▼──────────┐      ┌────────────────▼────────┐  │
│    │    Core State           │      │    Game Mechanics       │  │
│    │                         │      │                         │  │
│    │  game_state.py          │      │  casting.py             │  │
│    │  player.py              │      │  stack.py               │  │
│    │  zones.py               │      │  combat.py              │  │
│    │  mana.py                │      │  abilities.py           │  │
│    │  types.py               │      │  triggers.py            │  │
│    │  card.py                │      │  continuous_effects.py  │  │
│    │                         │      │  replacement_effects.py │  │
│    │                         │      │  state_based_actions.py │  │
│    │                         │      │  protection.py          │  │
│    └─────────────────────────┘      └─────────────────────────┘  │
│                   │                                              │
│    ┌──────────────▼───────────────────────────────────────────┐  │
│    │                    Card Layer                            │  │
│    │                                                          │  │
│    │  cards/registry.py   — CardRegistry + CardMetadata       │  │
│    │  cards/scryfall.py   — Scryfall API fetch + cache        │  │
│    │  cards/fdn/          — FDN set (264 per-card dirs)       │  │
│    │    {collector_number}/card_impl.py  — implementation     │  │
│    │    {collector_number}/card_spec.json — card metadata     │  │
│    │  cards/sos/          — SOS set (346 per-card dirs)       │  │
│    │    {collector_number}/card_impl.py  — implementation     │  │
│    │    {collector_number}/card_spec.json — card metadata     │  │
│    │  cards/foundations/   — FDN source implementations       │  │
│    └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Data & Scripts                                                  │
│                                                                  │
│  data/sets/              — Scryfall JSON cache                   │
│  data/replays/           — Card ID map + sample replay data      │
│  scripts/build_card_id_map.py — Scryfall → card_id_map.json      │
└──────────────────────────────────────────────────────────────────┘
```

## Directory Structure

| Directory | Status | Purpose | Summary |
|-----------|--------|---------|---------|
| `engine/` | [Completed] | Core game engine (17 modules) | [engine/DIRECTORY_SUMMARY.md](engine/DIRECTORY_SUMMARY.md) |
| `cards/` | [Completed] | Card registry and data pipeline | [cards/DIRECTORY_SUMMARY.md](cards/DIRECTORY_SUMMARY.md) |
| `cards/foundations/` | [Completed] | FDN set source implementations (260+ cards, 21 files) | [cards/foundations/DIRECTORY_SUMMARY.md](cards/foundations/DIRECTORY_SUMMARY.md) |
| `cards/fdn/` | [Completed] | FDN per-card directories (264 cards) | Per-card card_impl.py + card_spec.json |
| `cards/sos/` | [Completed] | SOS per-card directories (346 cards) | Per-card card_impl.py + card_spec.json |
| `silverquillm/` | [Completed] | **Benchmark runner package** | [silverquillm/DIRECTORY_SUMMARY.md](silverquillm/DIRECTORY_SUMMARY.md) |
| `silverquillm/replay/` | [Completed] | **Replay validation pipeline** (7 modules) | [silverquillm/replay/DIRECTORY_SUMMARY.md](silverquillm/replay/DIRECTORY_SUMMARY.md) |
| `docker/` | [Completed] | **Docker container images** for agent execution | |
| `docker/opencode-tested/` | [Completed] | OpenCode tested-phase container | entrypoint.sh + progress.jsonl |
| `docker/opencode-blind/` | [Completed] | OpenCode blind-phase container | entrypoint.sh + progress.jsonl |
| `benchmarks/` | [Completed] | Benchmark data sets (namespace package) | [benchmarks/DIRECTORY_SUMMARY.md](benchmarks/DIRECTORY_SUMMARY.md) |
| `benchmarks/sos/` | [Completed] | SOS benchmark set (346 cards) | [benchmarks/sos/DIRECTORY_SUMMARY.md](benchmarks/sos/DIRECTORY_SUMMARY.md) |
| `data/` | [Completed] | Runtime data cache + replay data | [data/DIRECTORY_SUMMARY.md](data/DIRECTORY_SUMMARY.md) |
| `data/replays/` | [Completed] | Card ID mapping + sample replays | (covered in data/ summary) |
| `scripts/` | [Completed] | Utility scripts (card ID map builder) | [scripts/DIRECTORY_SUMMARY.md](scripts/DIRECTORY_SUMMARY.md) |
| `tests/` | [Completed] | Test root + benchmark module tests + utilities | [tests/DIRECTORY_SUMMARY.md](tests/DIRECTORY_SUMMARY.md) |
| `tests/engine/` | [Completed] | Engine module unit tests (25 test files) | [tests/engine/DIRECTORY_SUMMARY.md](tests/engine/DIRECTORY_SUMMARY.md) |
| `tests/cards/` | [Completed] | Card implementation tests (26 test files) | [tests/cards/DIRECTORY_SUMMARY.md](tests/cards/DIRECTORY_SUMMARY.md) |
| `tests/benchmark/` | [Completed] | Integration tests + helpers for full pipeline | [tests/benchmark/DIRECTORY_SUMMARY.md](tests/benchmark/DIRECTORY_SUMMARY.md) |
| `docs/` | [Completed] | Documentation, specs, agent reference docs | [docs/DIRECTORY_SUMMARY.md](docs/DIRECTORY_SUMMARY.md) |

## Dependency Flow

```
types.py (no deps — foundation enums/dataclasses, incl. HybridManaSymbol)
    ↑
zones.py, mana.py (depend on types)
    ↑
player.py (depends on types, zones, mana)
    ↑
card.py (depends on types)
    ↑
protection.py (depends on types, card — DEBT mnemonic helpers)
    ↑
game_state.py (depends on player, zones, stack, triggers, combat, continuous_effects, replacement_effects; has extra_turns queue)
    ↑
stack.py, casting.py, combat.py, abilities.py, triggers.py (depend on game_state, card, types, protection)
    ↑
state_based_actions.py, continuous_effects.py, replacement_effects.py (depend on game_state, card, zones, protection)
    ↑
turn.py, game.py (depend on all of the above — top-level orchestration)
    ↑
cards/ (depends on engine/ — implements CardImpl subclasses)
    ↑
silverquillm/ (depends on engine/ for AST extraction and agent context; uses benchmarks/ for data)
    ↑
docker/ (standalone Docker images — contain agent tools, invoked via subprocess)
silverquillm/replay/ (depends on engine/ for execution, data/replays/ for card ID maps)
```

## Key Patterns

- **DeterministicPlayer**: All tests use scripted player choices (FIFO queue) for reproducibility.
- **Identity-based zone lookups**: `contains()` / `remove()` use `is` (not `==`) for game object identity.
- **Auto-registration**: Triggers and replacement effects auto-register when permanents ETB and auto-unregister when they leave.
- **Centralized zone transitions**: `move_to_zone()` in `zones.py` handles replacement effects, event firing, and trigger registration/unregistration for all zone moves. `destroy()`, `sacrifice()`, `exile()` delegate to it.
- **Layer system**: Continuous effects reset objects to base characteristics then reapply in layer order (idempotent).
- **Owner vs. Controller**: Cards always go to owner's graveyard per MTG rules.
- **Converge support**: `mana.py` tracks `last_payment_colors` and `casting.py` stores `colors_spent`.
- **Hybrid mana**: `HybridManaSymbol` in `types.py`; backtracking resolution in `mana.py`.
- **Cost reduction**: `CardImpl.cost_reduction(game)` hook; applied in `casting.py` before mana payment.
- **Protection (DEBT)**: `protection.py` implements Damage, Enchanting/Equipping, Blocking, Targeting checks; integrated into `combat.py`, `casting.py`, `game.py`, `state_based_actions.py`.
- **Extra turns**: FIFO queue in `GameState.extra_turns`; pops without advancing normal rotation.
- **Docker container isolation**: Agent tools run inside Docker containers; host runner uses `docker` CLI via subprocess (no `docker` Python package).
- **Image-as-config**: The Docker image encapsulates all agent configuration — no separate `config.yaml` needed.
- **Dual tier keys**: Both `tier` and `complexity_tier` supported; prefer `complexity_tier` in new code.
- **Prompt templates**: Use `str.format_map` with `{placeholder}` — no f-strings with complex logic.
- **Subprocess isolation**: Benchmark evaluation runs pytest in subprocesses — implementations never imported into runner.
- **Persistent engine**: Engine directory writable across cards within a run; per-card diffs captured.
- **Postmortem logging**: JSONL logging per agent run; `agent_thoughts.md` narrative generated.
- **3-dimension evaluation**: SOS Card Correctness, FDN Regression, Engine Regression.
- **Replay validation**: 17lands GRE replay parsing → engine execution → divergence detection. Dual-seat model (Seat 1 validated, Seat 2 oracle-injected).

## Testing

- **Framework**: pytest
- **Total tests**: ~3,200+ test functions across 100+ test files
- **Test utilities**: `tests/test_utils.py` provides `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`, `declare_blockers`
- **Integration tests**: `tests/test_integration.py` runs end-to-end multi-turn game scenarios
- **Benchmark tests**: Each `silverquillm/` module has a corresponding `tests/test_*.py` file
- **Adapter tests**: Each adapter has a dedicated test file (`test_*_adapter.py`)
- **E2E integration tests**: `tests/benchmark/test_e2e.py` runs full-pipeline integration tests with mock agents
- **Engine extension tests**: `tests/test_engine_extensions.py` covers Converge mana color tracking
- **Card tests**: 26 test files in `tests/cards/` covering all 260+ card implementations
- **Replay tests**: `tests/test_replay_parser.py`, `tests/test_replay_executor.py`, `tests/test_divergence_detection.py` — 105 tests for the replay validation pipeline
- **Coverage**: Every engine module, card category, adapter, runner module, and replay module has dedicated tests
- **conftest.py**: Filters out benchmark functions that pytest would incorrectly collect as tests

## Build & Config

- **pyproject.toml**: setuptools build, Python ≥3.12, deps: requests, pyyaml, click; dev: pytest, ruff, mypy
- **ruff.toml**: Line length 100, target py312
- **Type checking**: PEP 561 py.typed markers in `engine/` and `cards/`
- **CLI entry point**: `silverquillm` command → `silverquillm.cli:main` (also available as `benchmark` for backward compat)
- **Docker images**: Agent-specific Docker images in `docker/` — the image IS the config
- **Setup questions**: `setup_questions.json` — Question bank for agent validation
