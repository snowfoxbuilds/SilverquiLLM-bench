# Project Map — SilverquiLLM-bench

## Overview

SilverquiLLM-bench is a **Magic: The Gathering game engine** built in Python, designed as a benchmark for evaluating LLM coding capabilities. The engine implements core MTG rules (comprehensive rules §100–§700+) for two-player games using cards from the **Foundations (FDN)** set.

The project includes a **benchmark runner package** (`benchmark/`) that orchestrates the full evaluation pipeline: classifying cards by complexity, generating specs and prompts for LLM agents, managing agent sessions, evaluating implementations, scoring results, and recording artifacts. The first benchmark set is **Shadows over Sonnenthal (SOS)** with 368 cards.

The codebase is ~30,000+ lines across source and tests, with **~1,400+ test functions** providing thorough coverage of all engine subsystems and the benchmark pipeline.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Benchmark Runner                         │
│  benchmark/cli.py — CLI entry point (run/eval/score/cards)   │
│  benchmark/config.py — YAML config loading                   │
│  benchmark/agent_session.py — workspace + agent orchestration│
└──────────────┬──────────────────────────────────┬────────────┘
               │                                  │
    ┌──────────▼──────────┐            ┌──────────▼──────────┐
    │  Card Pipeline       │            │  Eval Pipeline       │
    │                      │            │                      │
    │ card_classifier.py   │            │ evaluator.py         │
    │ card_spec.py         │            │ scorer.py            │
    │ template_gen.py      │            │ results.py           │
    │ docs_gen.py          │            │                      │
    │ rules_skill.py       │            │                      │
    │ prompts.py           │            │                      │
    │ prototype.py         │            │                      │
    └──────────────────────┘            └──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Game Loop                             │
│  engine/game.py — create_game, run_game, helper actions      │
│  engine/turn.py — run_turn, phase/step progression           │
└──────────────┬──────────────────────────────────┬────────────┘
               │                                  │
    ┌──────────▼──────────┐            ┌──────────▼──────────┐
    │    Core State        │            │   Game Mechanics     │
    │                      │            │                      │
    │ game_state.py        │            │ casting.py           │
    │ player.py            │            │ stack.py             │
    │ zones.py             │            │ combat.py            │
    │ mana.py              │            │ abilities.py         │
    │ types.py             │            │ triggers.py          │
    │ card.py              │            │ continuous_effects.py │
    │                      │            │ replacement_effects.py│
    │                      │            │ state_based_actions.py│
    └──────────────────────┘            └──────────────────────┘
               │
    ┌──────────▼──────────────────────────────────────────────┐
    │                   Card Layer                             │
    │                                                          │
    │ cards/registry.py — CardRegistry + CardMetadata          │
    │ cards/scryfall.py — Scryfall API fetch + cache           │
    │ cards/foundations/ — FDN set card implementations         │
    │   basic_lands.py — Plains, Island, Swamp, Mountain, Forest│
    │   simple_creatures.py — 15 vanilla/French vanilla creatures│
    │   simple_spells.py — 10 instants and sorceries           │
    │   simple_permanents.py — 5 enchantments and artifacts    │
    └─────────────────────────────────────────────────────────┘
```

## Directory Structure

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `engine/` | Core game engine (16 modules) | types.py, game_state.py, card.py, game.py, combat.py, mana.py (Converge support), casting.py (colors_spent tracking) |
| `cards/` | Card registry and data pipeline | registry.py, scryfall.py |
| `cards/foundations/` | FDN set card implementations (35 cards) | basic_lands.py, simple_creatures.py, simple_spells.py, simple_permanents.py |
| `benchmark/` | **Benchmark runner package** (14 modules) | cli.py, config.py, card_classifier.py, card_spec.py, template_gen.py, docs_gen.py, rules_skill.py, prompts.py, agent_session.py, evaluator.py, scorer.py, results.py, prototype.py |
| `benchmarks/` | Benchmark data sets (namespace package) | `__init__.py` |
| `benchmarks/sos/` | SOS benchmark set (368 cards) | fetch_data.py, prototype_cards.json, prototype_gaps.md |
| `benchmarks/sos/data/` | SOS raw/processed data | sos.json, sos_classified.json, comprehensive_rules.txt, rules_overview.md |
| `benchmarks/sos/cards/` | Per-card spec directories (368 dirs) | `{n}/card_spec.json` for each card |
| `benchmarks/sos/results/` | Benchmark run outputs | Per-run isolated directories |
| `tests/` | Test root + benchmark module tests + utilities | test_utils.py, test_integration.py, conftest.py, 15+ benchmark test files |
| `tests/engine/` | Engine module unit tests (20 test files) | One test file per engine module |
| `tests/cards/` | Card implementation tests (6 test files) | test_simple_creatures.py, test_simple_spells.py, etc. |
| `docs/` | Documentation, specs, and agent reference docs | specs/ (6 spec docs), engine_api.md, test_utils.md |
| `data/` | Runtime data cache | data/sets/ (Scryfall JSON cache) |

## Dependency Flow

```
types.py (no deps — foundation enums/dataclasses)
    ↑
zones.py, mana.py (depend on types)
    ↑
player.py (depends on types, zones, mana)
    ↑
card.py (depends on types)
    ↑
game_state.py (depends on player, zones, stack, triggers, combat, continuous_effects, replacement_effects)
    ↑
stack.py, casting.py, combat.py, abilities.py, triggers.py (depend on game_state, card, types)
    ↑
state_based_actions.py, continuous_effects.py, replacement_effects.py (depend on game_state, card, zones)
    ↑
turn.py, game.py (depend on all of the above — top-level orchestration)
    ↑
cards/ (depends on engine/ — implements CardImpl subclasses)
    ↑
benchmark/ (depends on engine/ for AST extraction and agent context; uses benchmarks/ for data)
```

## Key Patterns

- **DeterministicPlayer**: All tests use scripted player choices (FIFO queue) for reproducibility.
- **Identity-based zone lookups**: `contains()` / `remove()` use `is` (not `==`) for game object identity.
- **Auto-registration**: Triggers and replacement effects auto-register when permanents enter the battlefield (via `casting.py`) and auto-unregister when they leave (via `state_based_actions.py`).
- **Layer system**: Continuous effects reset objects to base characteristics then reapply all effects in layer order (idempotent).
- **Owner vs. Controller**: Cards always go to owner's graveyard per MTG rules, even if controlled by another player.
- **Converge support**: `mana.py` tracks `last_payment_colors` and `casting.py` stores `colors_spent` on cards after mana payment.
- **Prompt templates**: Use `str.format_map` with `{placeholder}` — no f-strings with complex logic.
- **Subprocess isolation**: Benchmark evaluation runs pytest in subprocesses — agent implementations are never imported into the runner.

## Testing

- **Framework**: pytest
- **Total tests**: ~1,400+ test functions across 35+ test files
- **Test utilities**: `tests/test_utils.py` provides `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`, `declare_blockers`
- **Integration tests**: `tests/test_integration.py` runs 9 end-to-end multi-turn game scenarios
- **Benchmark tests**: Each `benchmark/` module has a corresponding `tests/test_*.py` file
- **Engine extension tests**: `tests/test_engine_extensions.py` covers Converge mana color tracking
- **Coverage**: Every engine module has a dedicated test file; card implementations have per-category test files; all benchmark modules are tested
- **conftest.py**: Filters out benchmark functions (like `test_informed_prompt`) that pytest would incorrectly collect as tests

## Build & Config

- **pyproject.toml**: setuptools build, Python ≥3.12, deps: requests, pyyaml, click; dev: pytest, ruff, mypy
- **ruff.toml**: Line length 100, target py312
- **Type checking**: PEP 561 py.typed markers in both `engine/` and `cards/`
- **CLI entry point**: `benchmark` command (defined in `[project.scripts]`)
- **Config**: `config.example.yaml` provides example YAML configuration for benchmark runs
