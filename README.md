# SilverquiLLM-bench

A benchmark for evaluating LLM coding agents by tasking them with implementing **Magic: The Gathering** cards as Python classes in a custom game engine.

By using cards from the **newest MTG set** (not yet in training data), we minimize data contamination and measure genuine code-generation ability rather than memorization.

---

## Why MTG Cards?

Magic cards are ideal coding benchmarks because they:

- **Span a wide difficulty range** — from vanilla creatures (trivial) to complex planeswalkers with multiple loyalty abilities (expert)
- **Require understanding specs** — cards have precise rules text that must be translated into working code
- **Test architectural thinking** — agents must extend the engine with reusable mechanics, not one-off hacks
- **Have a natural test surface** — each card's behavior is well-defined and testable
- **Resist memorization** — new sets release quarterly with novel mechanics

---

## How It Works

```
Card Specs ──▶ Agent Session ──▶ Evaluation

• Card JSON specs         • Sandboxed workspace        • Self-eval (agent's own tests)
• Complexity tiers        • Step 1: Blind impl          • Cross-eval (other agents' tests)
• Engine API docs         • Step 2: Test-informed       • Audited eval (gold-standard tests)
• Base class templates    • Contamination guard         • Tier-weighted scoring
                          • Engine regression check
```

### Step 1: Blind Implementation

The agent receives a card spec, engine API docs, base classes, and reference implementations. It writes an implementation from scratch with **no test feedback**.

### Step 2: Test-Informed Iteration

The agent writes tests for its implementation, then iterates up to 3 rounds — running pytest and fixing failures each round.

### Persistent Engine

Cards are processed sequentially with a **shared, writable engine**. The agent can extend the engine (e.g., add a Ward mechanic) and those changes carry forward to future cards. After each card, all previous cards' tests are re-run to detect regressions.

---

## Current Benchmark Set

**Secrets of Strixhaven (SOS)** — released 2026-04-24

| Subset | Cards |
| --- | --- |
| SOS Base Set | 271 |
| SOA Mystical Archives | 65 |
| SPG Special Guests | 10 |
| **Total** | **346** |

Cards are classified into 5 complexity tiers: **trivial → simple → medium → complex → expert** based on keyword count, ability types, and rules text complexity.

---

## Project Structure

```
engine/                 Core MTG rules engine
├── game.py             Game state, turns, priority
├── card.py             CardImpl base classes
├── combat.py           Combat phases & damage
├── stack.py            Spell/ability stack (LIFO)
├── mana.py             Mana system (5 colors + colorless)
├── zones.py            Library, hand, battlefield, graveyard, exile, etc.
└── effects.py          Continuous effects (layer system)

cards/                  Card implementations
├── foundations/         FDN base set (~264 cards, reference implementations)
└── registry.py         Card registration system

silverquillm/           Benchmark runner package
├── cli.py              CLI entry point (run, eval, score, validate)
├── agent_session.py    Workspace setup, contamination controls, two-phase flow
├── adapters/           Agent tool adapters (opencode, claude_code, aider, pi)
├── prompts.py          Parameterized prompt templates
├── evaluator.py        Self-eval, cross-eval, audited eval
├── scorer.py           Tier-weighted scoring & leaderboard
├── replay/             Deterministic replay validation
└── config.py           YAML config loading

benchmarks/sos/         SOS benchmark data
├── cards/              346 card specs (card_spec.json per card)
├── data/               Scryfall data, classified tiers, rules
├── prototype_cards.json  5-card prototype subset for quick testing
└── results/            Per-run results directories

tests/                  ~1,400+ test functions across 35+ files
docs/                   Specs, engine API reference, design docs
```

---

## Quickstart

### Prerequisites

- Python ≥ 3.12
- [OpenCode](https://github.com/nicepkg/opencode) (or another supported agent tool)

### Install

```
git clone https://github.com/snowfoxbuilds/SilverquiLLM-bench.git
cd SilverquiLLM-bench
pip install -e ".[dev]"
```

### Configure

Create a `config.yaml`:

```
name: "SOS Benchmark"
set_code: "SOS"
model_name: "gemma-4-27b"
model_provider: "google"
max_context: 200000
temperature: 0.0
agent:
  adapter: "opencode"
  max_test_rounds: 3
  timeout_per_card: 300
  disable_web_search: true
output_dir: "benchmarks/sos/results"
```

### Run

```
# Dry run — preview selected cards
benchmark run --config config.yaml --dry-run

# Run prototype subset (5 cards, ~30 min)
benchmark run --config config.yaml --prototype

# Run specific cards by ID
benchmark run --config config.yaml --cards 6,11,97

# Full run (all 346 cards)
benchmark run --config config.yaml
```

### Evaluate

```
# Self-eval on a completed run
benchmark eval --results-dir benchmarks/sos/results/<run_name>/

# Audited eval with gold-standard tests
benchmark eval --results-dir benchmarks/sos/results/<run_name>/ --audited-dir benchmarks/sos/cards

# Score and generate leaderboard
benchmark score --results-dir benchmarks/sos/results/
```

### Validate Replays

```
# Validate deterministic replay for a card
benchmark validate benchmarks/sos/cards/6/ --verbose

# Validate all cards, stop on first divergence
benchmark validate benchmarks/sos/cards/ --cards --stop-on-divergence
```

---

## Agent Adapters

The runner supports multiple coding agents via a pluggable adapter pattern:

| Adapter | Tool | Notes |
| --- | --- | --- |
| `opencode` | [OpenCode](https://github.com/nicepkg/opencode) | Default. Tool-calling via OpenAI-compatible API |
| `claude_code` | Claude Code | Anthropic's native CLI agent |
| `aider` | [Aider](https://github.com/paul-gauthier/aider) | Text-based edits, good for models without tool-calling |
| `pi` | Pi | General-purpose coding agent |

Set via `agent.adapter` in config. Each adapter translates prompts into the tool's native interface and captures output for postmortem logging.

---

## Scoring

Implementations are scored across multiple categories, weighted by card complexity tier:

| Category | What It Measures |
| --- | --- |
| **Blind Implementation** | Can the agent implement a card from just the spec and engine docs? |
| **Test-Informed Implementation** | Can it fix its implementation given test feedback? |
| **Test Quality** | How good are the tests the agent writes? (measured by audited eval survival) |
| **Engine Quality** | Are engine extensions generic and regression-free? |

Complexity tier weights ensure that implementing a mythic rare with 5 keyword abilities scores higher than a vanilla 2/2.

---

## Game Engine

The engine implements core MTG rules (Comprehensive Rules §100–§700+) for two-player games:

- **Turn structure** — untap, upkeep, draw, main phases, combat (declare attackers/blockers/damage), end step, cleanup
- **Stack & priority** — spell casting, ability activation, LIFO resolution
- **Combat** — first/double strike, trample, damage assignment
- **Mana system** — 5 colors + colorless, mana pools
- **Zones** — library, hand, battlefield, graveyard, stack, exile, command zone
- **Type system** — all MTG card types, subtypes, supertypes
- **Continuous effects** — layer system (1–7) with timestamp ordering
- **Triggered abilities** — auto-register on ETB, auto-unregister on leave
- **State-based actions** — creature death, legend rule, etc.

Card implementations subclass `CardImpl` (or `Creature`, `Instant`, `Sorcery`, etc.) and use hook methods to define abilities. See `docs/engine_api.md` for the full API.

---

## Contamination Controls

1. **No web access** — agents cannot fetch external resources
2. **Fresh workspace per card** — isolated `.workspace/` directory with only permitted files
3. **New set cards** — SOS released 2026-04-24, too new for LLM training data
4. **No cross-agent leakage** — each model gets its own run with a fresh engine copy
5. **Protected directories** — runner detects and rejects modifications outside the workspace
6. **Engine regression gate** — all previous cards' tests re-run after each card

---

## Output Artifacts

Each run produces a self-contained results directory:

```
results/<run_name>/
├── config.yaml                  # Snapshot of run configuration
├── summary.json                 # Aggregate stats
├── raw_agent_log.jsonl          # Full untruncated agent output
├── run_engine/                  # Engine state during run
├── engine_final/                # Final engine state
└── cards/
    └── <card_id>/
        ├── blind_impl.py        # Step 1 output
        ├── tested_impl.py       # Step 2 output
        ├── tests.py             # Agent-written tests
        ├── result.json          # Metrics & eval results
        ├── postmortem.jsonl     # Structured debug log
        ├── agent_thoughts.md    # Human-readable reasoning trace
        └── engine_diff.patch    # Engine changes for this card
```

---

## Running Tests

```
# Unit tests
pytest

# With coverage
pytest --cov=engine --cov=silverquillm

# Specific test file
pytest tests/test_combat.py -v
```

---

## Acknowledgments

The game engine is inspired by [XMage](https://github.com/magefree/mage), an open-source Magic: The Gathering simulator (MIT License). The Foundations (FDN) base set card implementations reference XMage's card logic.

## License

MIT — see [LICENSE](LICENSE) for details.
