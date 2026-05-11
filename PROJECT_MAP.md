# Project Map — SilverquiLLM-bench

## Overview

SilverquiLLM-bench is a **Magic: The Gathering game engine** built in Python, designed as a benchmark for evaluating LLM coding capabilities. The engine implements core MTG rules (comprehensive rules §100–§700+) for two-player games using cards from the **Foundations (FDN)** set.

The project includes a **benchmark runner package** (`silverquillm/`) that orchestrates the full evaluation pipeline: classifying cards by complexity, generating specs and prompts for LLM agents, managing agent sessions via pluggable adapters, evaluating implementations, scoring results (4 categories), and recording artifacts. The first benchmark set is **Shadows over Sonnenthal (SOS)** with 368 cards.

The project also includes a **replay validation pipeline** (`silverquillm/replay/`) that parses 17lands GRE replay data from real MTG Arena games and validates the engine's behavior against ground-truth game state snapshots, detecting divergences where the engine differs from the official game client.

The codebase is ~40,000+ lines across source and tests, with **~3,200+ test functions** providing thorough coverage of all engine subsystems, the benchmark pipeline, and the replay validation pipeline.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Benchmark Runner                           │
│  silverquillm/cli.py       — CLI entry point (run/eval/score/   │
│                               cards/validate)                    │
│  silverquillm/config.py    — YAML config + nested AgentConfig   │
│  silverquillm/agent_session.py — workspace + agent lifecycle    │
│                   │                                  │           │
│    ┌──────────────▼──────────┐      ┌────────────────▼────────┐ │
│    │    Card Pipeline        │      │    Eval Pipeline        │ │
│    │                         │      │                         │ │
│    │  card_classifier.py     │      │  evaluator.py           │ │
│    │  card_spec.py           │      │  scorer.py (4 cats)     │ │
│    │  card_loader.py         │      │  results.py             │ │
│    │  template_gen.py        │      │  run_utils.py           │ │
│    │  docs_gen.py            │      │  regression.py          │ │
│    │  rules_skill.py         │      │                         │ │
│    │  prompts.py             │      │                         │ │
│    │  prototype.py           │      │                         │ │
│    └─────────────────────────┘      └─────────────────────────┘ │
│                                                                  │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │    Replay Validation Pipeline                            │  │
│    │                                                          │  │
│    │  replay/types.py      — ReplayGame, GameSnapshot, etc.   │  │
│    │  replay/state.py      — GRE state reconstruction         │  │
│    │  replay/parser.py     — parse_replay() entry point       │  │
│    │  replay/executor.py   — ReplayExecutor (state-diff mode) │  │
│    │  replay/validation.py — Divergence detection & reporting  │  │
│    │  replay/cli.py        — `benchmark validate` subcommand  │  │
│    └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Agent Adapters (silverquillm/adapters/)                         │
│                                                                  │
│  base.py        — AgentAdapter ABC + registry + factory          │
│  opencode.py    — OpenCode CLI adapter                           │
│  claude_code.py — Claude Code CLI adapter                        │
│  aider.py       — Aider CLI adapter                              │
│  pi.py          — Pi CLI adapter                                 │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                         Game Loop                                │
│  engine/game.py — create_game, run_game, helper actions          │
│  engine/turn.py — run_turn, phase/step progression               │
│                   │                                  │           │
│    ┌──────────────▼──────────┐      ┌────────────────▼────────┐ │
│    │    Core State           │      │    Game Mechanics       │ │
│    │                         │      │                         │ │
│    │  game_state.py          │      │  casting.py             │ │
│    │  player.py              │      │  stack.py               │ │
│    │  zones.py               │      │  combat.py              │ │
│    │  mana.py                │      │  abilities.py           │ │
│    │  types.py               │      │  triggers.py            │ │
│    │  card.py                │      │  continuous_effects.py  │ │
│    │                         │      │  replacement_effects.py │ │
│    │                         │      │  state_based_actions.py │ │
│    │                         │      │  protection.py          │ │
│    └─────────────────────────┘      └─────────────────────────┘ │
│                   │                                              │
│    ┌──────────────▼──────────────────────────────────────────┐  │
│    │                    Card Layer                            │  │
│    │                                                          │  │
│    │  cards/registry.py   — CardRegistry + CardMetadata       │  │
│    │  cards/scryfall.py   — Scryfall API fetch + cache        │  │
│    │  cards/foundations/  — FDN set card implementations (260+)│  │
│    │    basic_lands.py        — 5 basic lands                 │  │
│    │    simple_creatures.py   — 15 vanilla/French vanilla     │  │
│    │    vanilla_creatures_batch2.py — 7 batch 2 creatures     │  │
│    │    simple_spells.py      — 10 instants/sorceries         │  │
│    │    simple_spells_batch2.py — 15 non-targeted spells      │  │
│    │    simple_spells_batch3.py — 18 targeted spells           │  │
│    │    simple_permanents.py  — 5 enchantments and artifacts  │  │
│    │    enchantments.py       — 8 enchantments (auras+global) │  │
│    │    auras_batch2.py       — 10 batch 2 auras              │  │
│    │    global_enchantments.py — 10 non-aura enchantments     │  │
│    │    planeswalkers.py      — 4 planeswalkers               │  │
│    │    planeswalkers_batch2.py — 3 batch 2 planeswalkers     │  │
│    │    modal_spells.py       — 8 modal spells                │  │
│    │    complex_spells.py     — 16 modal/X-cost/kicker cards  │  │
│    │    artifacts.py          — 10 artifacts (mana rocks, eq.)│  │
│    │    artifacts_batch2.py   — 27 batch 2 artifacts          │  │
│    │    equipment.py          — 7 equipment cards              │  │
│    │    lands.py              — 13 non-basic lands             │  │
│    │    etb_creatures.py      — 29 ETB trigger creatures       │  │
│    │    death_trigger_creatures.py — 17 death triggers        │  │
│    │    activated_creatures.py — 19 activated abilities        │  │
│    │    special_guests.py     — 10 Special Guest (SPG) cards  │  │
│    └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Data & Scripts                                                  │
│                                                                  │
│  data/sets/              — Scryfall JSON cache                   │
│  data/replays/           — Card ID map + sample replay data      │
│  scripts/build_card_id_map.py — Scryfall → card_id_map.json     │
└──────────────────────────────────────────────────────────────────┘
```

## Directory Structure

| Directory | Status | Purpose | Summary |
|-----------|--------|---------|---------|
| `engine/` | [Completed] | Core game engine (17 modules) | [engine/DIRECTORY_SUMMARY.md](engine/DIRECTORY_SUMMARY.md) |
| `cards/` | [Completed] | Card registry and data pipeline | [cards/DIRECTORY_SUMMARY.md](cards/DIRECTORY_SUMMARY.md) |
| `cards/foundations/` | [Completed] | FDN set card implementations (260+ cards, 21 files) | [cards/foundations/DIRECTORY_SUMMARY.md](cards/foundations/DIRECTORY_SUMMARY.md) |
| `silverquillm/` | [Completed] | **Benchmark runner package** (18+ modules) | [silverquillm/DIRECTORY_SUMMARY.md](silverquillm/DIRECTORY_SUMMARY.md) |
| `silverquillm/adapters/` | [Completed] | **Agent adapter system** (6 modules) | [silverquillm/adapters/DIRECTORY_SUMMARY.md](silverquillm/adapters/DIRECTORY_SUMMARY.md) |
| `silverquillm/replay/` | [Completed] | **Replay validation pipeline** (7 modules) | [silverquillm/replay/DIRECTORY_SUMMARY.md](silverquillm/replay/DIRECTORY_SUMMARY.md) |
| `benchmarks/` | [Completed] | Benchmark data sets (namespace package) | [benchmarks/DIRECTORY_SUMMARY.md](benchmarks/DIRECTORY_SUMMARY.md) |
| `benchmarks/sos/` | [Completed] | SOS benchmark set (368 cards) | [benchmarks/sos/DIRECTORY_SUMMARY.md](benchmarks/sos/DIRECTORY_SUMMARY.md) |
| `benchmarks/sos/data/` | [Completed] | SOS raw/processed data | (covered in sos/ summary) |
| `benchmarks/sos/cards/` | [Completed] | Per-card spec directories (368 dirs) | (covered in sos/ summary) |
| `benchmarks/sos/results/` | [Completed] | Benchmark run outputs | (covered in sos/ summary) |
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
silverquillm/adapters/ (depends on silverquillm/config — wraps external CLI tools)
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
- **Adapter pattern**: Agent tools wrapped via `AgentAdapter` ABC with registry-based factory (`get_adapter`).
- **Nested config**: Agent settings in `config.agent` (`AgentConfig` dataclass) — no flat top-level keys.
- **Dual tier keys**: Both `tier` and `complexity_tier` supported; prefer `complexity_tier` in new code.
- **Prompt templates**: Use `str.format_map` with `{placeholder}` — no f-strings with complex logic.
- **Subprocess isolation**: Benchmark evaluation runs pytest in subprocesses — implementations never imported into runner.
- **Persistent engine**: Engine directory writable across cards within a run; per-card diffs captured.
- **Postmortem logging**: JSONL logging per agent run; `agent_thoughts.md` narrative generated.
- **4-category scoring**: Blind, Tested, Audited, Engine Extension Quality.
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
- **CLI entry point**: `benchmark` command → `silverquillm.cli:main`
- **Config**: `config.example.yaml` — YAML config with nested `agent:` block including `adapter` field
- **Setup questions**: `setup_questions.json` — Question bank for agent validation
