# Project Map — SilverquiLLM-bench

## Overview

SilverquiLLM-bench is a **Magic: The Gathering game engine** built in Python, designed as a benchmark for evaluating LLM coding capabilities. The engine implements core MTG rules (comprehensive rules §100–§700+) for two-player games using cards from the **Foundations (FDN)** set.

The project includes a **benchmark runner package** (`silverquillm/`) that orchestrates the full evaluation pipeline: classifying cards by complexity, generating specs and prompts for LLM agents, managing agent sessions via pluggable adapters, evaluating implementations, scoring results (4 categories), and recording artifacts. The first benchmark set is **Shadows over Sonnenthal (SOS)** with 368 cards.

The codebase is ~35,000+ lines across source and tests, with **~1,800+ test functions** providing thorough coverage of all engine subsystems and the benchmark pipeline.

## Architecture

```

                     Benchmark Runner                         │
  silverquillm/cli. CLI entry point (run/eval/score/cards)│py 
  silverquillm/config.py — YAML config + nested AgentConfig   │
  silverquillm/agent_session.py — workspace + agent lifecycle  │

               │                                  │
    ┌──────────▼──────────┐            ┌──────────▼──────────┐
    │  Card Pipeline       │            │  Eval Pipeline       │
    │                      │            │                      │
    │ card_classifier.py   │            │ evaluator.py         │
    │ card_spec.py         │            │ scorer.py (4 cats)   │
    card_loader.py             │ results.py           ││       
    │ template_gen.py      │            │ run_utils.py         │
    │ docs_gen.py          │            │ regression.py        │
    │ rules_skill.py       │            │                      │
    │ prompts.py           │            │                      │
    │ prototype.py         │            │                      │
            └──────────────────────┘    └────────────────

    ┌─────────────────────────────────────────────────────────┐
    │  Agent Adapters (silverquillm/adapters/)                 │
    │                                                          │
    │  base.py — AgentAdapter ABC + registry + factory         │
    │  opencode.py — OpenCode CLI adapter                      │
    │  claude_code.py — Claude Code CLI adapter                │
    │  aider.py — Aider CLI adapter                            │
    pi.py  │ Pi CLI adapter                                  │ 
    └─────────────────────────────────────────────────────────┘


                        Game Loop                             │
  engine/game.py — create_game, run_game, helper actions      │
  engine/turn.py — run_turn, phase/step progression           │

               │                                  │
            ┌──────────▼──────────┐    ┌──────────▼───
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
    │ cards/foundations/ — FDN set card implementations (65+)   │
    │   basic_lands.py — 5 basic lands                         │
    │   simple_creatures.py — 15 vanilla/French vanilla        │
    │   simple_spells.py — 10 instants and sorceries           │
    │   simple_permanents.py — 5 enchantments and artifacts    │
    │   enchantments.py — 8 enchantments (auras + global)      │
    │   planeswalkers.py — 4 planeswalkers                     │
    │   modal_spells.py — 8 modal spells                       │
    │   artifacts.py — 10 artifacts (mana rocks, equipment)    │
    └─────────────────────────────────────────────────────────┘
```

## Directory Structure

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `engine/` | Core game engine (16 modules) | types.py, game_state.py, card.py, game.py, combat.py, mana.py, casting.py |
| `cards/` | Card registry and data pipeline | registry.py, scryfall.py |
| `cards/foundations/` | FDN set card implementations (65+ cards, 7 categories) | basic_lands.py, simple_creatures.py, simple_spells.py, simple_permanents.py, enchantments.py, planeswalkers.py, modal_spells.py, artifacts.py |
| `silverquillm/` | **Benchmark runner package** (18 modules) | cli.py, config.py, agent_session.py, card_loader.py, card_classifier.py, card_spec.py, template_gen.py, docs_gen.py, rules_skill.py, prompts.py, run_utils.py, evaluator.py, scorer.py, results.py, prototype.py, regression.py, setup_questions.py |
| `silverquillm/adapters/` | **Agent adapter system** (6 modules) | base.py, opencode.py, claude_code.py, aider.py, pi.py |
| `benchmarks/` | Benchmark data sets (namespace package) | `__init__.py` |
| `benchmarks/sos/` | SOS benchmark set (368 cards) | fetch_data.py, prototype_cards.json, prototype_gaps.md |
| `benchmarks/sos/data/` | SOS raw/processed data | sos.json, sos_classified.json, comprehensive_rules.txt, rules_overview.md |
| `benchmarks/sos/cards/` | Per-card spec directories (368 dirs) | `{n}/card_spec.json` for each card |
| `benchmarks/sos/results/` | Benchmark run outputs | Per-run isolated directories |
| `tests/` | Test root + benchmark module tests + utilities | test_utils.py, test_integration.py, conftest.py, 45+ test files |
| `tests/engine/` | Engine module unit tests (20 test files) | One test file per engine module |
| `tests/cards/` | Card implementation tests (12 test files) | Per-category + integration tests |
| `tests/benchmark/` | Integration tests + helpers for full pipeline | test_helpers.py, test_e2e.py |
| `docs/` | Documentation, specs, agent reference docs | specs/ (6 spec docs), engine_api.md, test_utils.md |
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
silverquillm/ (depends on engine/ for AST extraction and agent context; uses benchmarks/ for data)
    ↑
silverquillm/adapters/ (depends on silverquillm/config — wraps external CLI tools)
```

## Key Patterns

- **DeterministicPlayer**: All tests use scripted player choices (FIFO queue) for reproducibility.
- **Identity-based zone lookups**: `contains()` / `remove()` use `is` (not `==`) for game object identity.
- **Auto-registration**: Triggers and replacement effects auto-register when permanents ETB and auto-unregister when they leave.
- **Layer system**: Continuous effects reset objects to base characteristics then reapply in layer order (idempotent).
- **Owner vs. Controller**: Cards always go to owner's graveyard per MTG rules.
- **Converge support**: `mana.py` tracks `last_payment_colors` and `casting.py` stores `colors_spent`.
- **Adapter pattern**: Agent tools wrapped via `AgentAdapter` ABC with registry-based factory (`get_adapter`).
- **Nested config**: Agent settings in `config.agent` (`AgentConfig` dataclass) — no flat top-level keys.
- **Dual tier keys**: Both `tier` and `complexity_tier` supported; prefer `complexity_tier` in new code.
- **Prompt templates**: Use `str.format_map` with `{placeholder}` — no f-strings with complex logic.
- **Subprocess isolation**: Benchmark evaluation runs pytest in subprocesses — implementations never imported into runner.
- **Persistent engine**: Engine directory writable across cards within a run; per-card diffs captured.
- **Postmortem logging**: JSONL logging per agent run; `agent_thoughts.md` narrative generated.
- **4-category scoring**: Blind, Tested, Audited, Engine Extension Quality.

## Testing

- **Framework**: pytest
- **Total tests**: ~1,800+ test functions across 55+ test files
- **Test utilities**: `tests/test_utils.py` provides `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`, `declare_blockers`
- **Integration tests**: `tests/test_integration.py` runs end-to-end multi-turn game scenarios
- **Benchmark tests**: Each `silverquillm/` module has a corresponding `tests/test_*.py` file
- **Adapter tests**: Each adapter has a dedicated test file (`test_*_adapter.py`)
- **E2E integration tests**: `tests/benchmark/test_e2e.py` runs full-pipeline integration tests with mock agents
- **Engine extension tests**: `tests/test_engine_extensions.py` covers Converge mana color tracking
- **Card tests**: 12 test files in `tests/cards/` covering all 65+ card implementations
- **Coverage**: Every engine module, card category, adapter, and runner module has dedicated tests
- **conftest.py**: Filters out benchmark functions that pytest would incorrectly collect as tests

## Build & Config

- **pyproject.toml**: setuptools build, Python ≥3.12, deps: requests, pyyaml, click; dev: pytest, ruff, mypy
- **ruff.toml**: Line length 100, target py312
- **Type checking**: PEP 561 py.typed markers in `engine/` and `cards/`
- **CLI entry point**: `benchmark` command → `silverquillm.cli:main`
- **Config**: `config.example.yaml` — YAML config with nested `agent:` block including `adapter` field
- **Setup questions**: `setup_questions.json` — Question bank for agent validation
