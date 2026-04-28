# Project Map — SilverquiLLM-bench

## Overview

SilverquiLLM-bench is a **Magic: The Gathering game engine** built in Python, designed as a benchmark for evaluating LLM coding capabilities. The engine implements core MTG rules (comprehensive rules §100–§700+) for two-player games using cards from the **Foundations (FDN)** set.

The codebase is ~24,000 lines across source and tests, with **1,119 test functions** providing thorough coverage of all engine subsystems.

## Architecture

```
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
| `engine/` | Core game engine (16 modules) | types.py, game_state.py, card.py, game.py, combat.py |
| `cards/` | Card registry and data pipeline | registry.py, scryfall.py |
| `cards/foundations/` | FDN set card implementations (35 cards) | basic_lands.py, simple_creatures.py, simple_spells.py, simple_permanents.py |
| `tests/` | Test root + integration tests + test utilities | test_integration.py, test_utils.py, test_scaffold.py |
| `tests/engine/` | Engine module unit tests (20 test files) | One test file per engine module |
| `tests/cards/` | Card implementation tests (6 test files) | test_simple_creatures.py, test_simple_spells.py, etc. |
| `docs/` | Documentation and spec files | docs/specs/ (6 spec documents) |
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
```

## Key Patterns

- **DeterministicPlayer**: All tests use scripted player choices (FIFO queue) for reproducibility.
- **Identity-based zone lookups**: `contains()` / `remove()` use `is` (not `==`) for game object identity.
- **Auto-registration**: Triggers and replacement effects auto-register when permanents enter the battlefield (via `casting.py`) and auto-unregister when they leave (via `state_based_actions.py`).
- **Layer system**: Continuous effects reset objects to base characteristics then reapply all effects in layer order (idempotent).
- **Owner vs. Controller**: Cards always go to owner's graveyard per MTG rules, even if controlled by another player.

## Testing

- **Framework**: pytest
- **Total tests**: ~1,119 test functions across 26 test files
- **Test utilities**: `tests/test_utils.py` provides `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`, `declare_blockers`
- **Integration tests**: `tests/test_integration.py` runs 9 end-to-end multi-turn game scenarios
- **Coverage**: Every engine module has a dedicated test file; card implementations have per-category test files

## Build & Config

- **pyproject.toml**: setuptools build, Python ≥3.10, deps: requests; dev: pytest, ruff, mypy
- **ruff.toml**: Line length 100, target py311
- **Type checking**: PEP 561 py.typed markers in both `engine/` and `cards/`
