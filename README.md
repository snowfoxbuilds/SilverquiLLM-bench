# SilverquiLLM-bench

A benchmark for evaluating LLM coding ability by tasking models with implementing **Magic: The Gathering** cards as Python classes in a custom game engine.

The key insight: by using cards from the **newest MTG set** (not yet in training data), we minimize data contamination and measure genuine code-generation ability rather than memorization.

## How It Works

```
┌────────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│   Card Specs        │     │   Agent Session       │     │   Evaluation      │
│                     │     │                       │     │                   │
│ • Card JSON specs   │────▶│ • Sandboxed workspace │────▶│ • Self-eval       │
│ • Complexity tiers  │     │ • Blind impl pass     │     │ • Cross-eval      │
│ • Engine API docs   │     │ • Test-informed pass  │     │ • Audited tests   │
│ • Base class templates│   │ • Contamination guard │     │ • Tier-weighted   │
└────────────────────┘     └──────────────────────┘     │   scoring         │
                                                        └──────────────────┘
```

1. **Card Pipeline** — Cards are classified by complexity tier, and each gets a structured spec with rules text, type info, keywords, and a generated code template.
2. **Agent Session** — An LLM agent (via [OpenCode](https://github.com/nicepkg/opencode)) gets the card spec, engine API docs, and base classes in an isolated workspace. It first writes a "blind" implementation, then iterates with test feedback.
3. **Evaluation** — Implementations are scored across three categories: blind implementation quality, test-informed implementation, and test quality. Scores are weighted by card complexity tier.

## Current Benchmark Set

**Shadows over Sonnenthal (SOS)** — 368 cards, released 2026-04-24. Cards are classified into 5 complexity tiers based on keyword count, ability types, and rules text complexity.

## Project Structure

```
engine/              Core MTG rules engine (types, game state, combat, stack, etc.)
cards/               Card registry, Scryfall data pipeline, Foundations set implementations
benchmark/           Benchmark runner package (CLI, agent sessions, eval, scoring)
benchmarks/sos/      SOS benchmark set (368 card specs, classified data, results)
tests/               ~1,400+ test functions across 35+ files
docs/                Specs, engine API reference, design docs
```

## Quickstart

### Prerequisites

- Python ≥ 3.12
- [OpenCode](https://github.com/nicepkg/opencode) (for running LLM agents)

### Install

```bash
git clone https://github.com/snowfoxsean/SilverquiLLM-bench.git
cd SilverquiLLM-bench
pip install -e ".[dev]"
```

### Configure

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your model and paths
```

### Run the Benchmark

```bash
# Dry run — list selected cards without executing
benchmark run --config config.yaml --dry-run

# Run on specific cards by collector number
benchmark run --config config.yaml --cards 011,006

# Run on prototype card subset
benchmark run --config config.yaml --prototype

# Full run (all 368 cards)
benchmark run --config config.yaml
```

### Evaluate & Score

```bash
# Run evaluation on existing results
benchmark eval --results-dir benchmarks/sos/results/

# Generate leaderboard and aggregate scores
benchmark score --results-dir benchmarks/sos/results/
```

### Run Tests

```bash
# Unit tests
pytest

# Integration tests
pytest -m integration

# With coverage
pytest --cov=engine --cov=benchmark
```

## Game Engine

The engine implements core MTG rules (Comprehensive Rules §100–§700+) for two-player games:

- **Turn structure** — Untap, upkeep, draw, main phases, combat (with full declare attackers/blockers/damage steps), end step, cleanup
- **Stack & priority** — Spell casting, ability activation, LIFO resolution
- **Combat** — Attackers, blockers, damage assignment, first/double strike, trample
- **Mana system** — 5 colors + colorless, mana pools, Converge tracking
- **Zones** — Library, hand, battlefield, graveyard, stack, exile, command zone
- **Type system** — All MTG card types, subtypes, supertypes
- **Continuous effects** — Layer system (1–7) with timestamp ordering
- **Triggered abilities** — Auto-register on ETB, auto-unregister on leave
- **State-based actions** — Creature death, legend rule, etc.

Card implementations subclass `CardImpl` and use hook methods to define abilities — see `docs/engine_api.md` for the full API reference.

## Scoring

Each model is scored across three categories, weighted by card complexity tier:

| Category | What It Measures |
|----------|------------------|
| **Blind Implementation** | Can the model implement a card from just the spec and engine docs? |
| **Test-Informed Implementation** | Can it fix its implementation given test feedback? |
| **Test Quality** | How good are the tests the model writes? |

Complexity tiers ensure that implementing a mythic rare with 5 keyword abilities counts more than a vanilla 2/2.

## Notion Spec Sync

The project uses Notion as the source of truth for design specs. To sync:

```bash
export NOTION_TOKEN=ntn_...
python sync_notion_specs.py --project-root-id <PAGE_ID> --output-dir ./
```

See `sync_notion_specs.py` for details on the Notion page structure.

## Acknowledgments

The game engine is inspired by [XMage](https://github.com/magefree/mage), an open-source Magic: The Gathering simulator (MIT License). The Foundations (FDN) base set card implementations reference XMage's card logic.

## License

MIT — see [LICENSE](LICENSE) for details.
