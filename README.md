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
Card Specs ──▶ Docker Container ──▶ Evaluation

• Card JSON specs         • Isolated Docker container      • SOS card correctness
• Complexity tiers        • Step 1: Blind impl              • FDN regression check
• Engine API docs         • Step 2: Test-informed            • Engine regression check
• Base class templates    • progress.jsonl monitoring        • Tier-weighted scoring
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
├── foundations/         FDN source implementations (~264 cards)
├── fdn/                FDN per-card dirs (card_impl.py + card_spec.json)
├── sos/                SOS per-card dirs (card_impl.py + card_spec.json)
└── registry.py         Card registration system

docker/                 Docker container images
├── opencode-tested/    OpenCode tested-phase image
│   └── entrypoint.sh   Card loop + progress.jsonl
└── opencode-blind/     OpenCode blind-phase image
    └── entrypoint.sh   Blind impl + progress.jsonl

silverquillm/           Benchmark runner package
├── cli.py              CLI entry point (run, smoke)
├── workspace.py        Workspace isolation + volume setup
├── card_loader.py      Card spec loading from per-card dirs
├── card_spec.py        Card spec dataclass + parsing
├── results.py          Per-card result collection
├── evaluator.py        SOS correctness, FDN regression, engine regression
└── replay/             Replay validation (not yet wired to new CLI)

benchmarks/sos/         SOS benchmark data
├── data/               Scryfall data, classified tiers, rules
└── results/            Per-run results directories

tests/                  ~3,200+ test functions across 100+ files
docs/                   Specs, engine API reference, design docs
```

---

## Quickstart

### Prerequisites

- Python ≥ 3.12
- Docker

### Install

```
git clone https://github.com/snowfoxbuilds/SilverquiLLM-bench.git
cd SilverquiLLM-bench
pip install -e ".[dev]"
```

### Build a Docker Image

Each agent/model combination is packaged as a Docker image. The image **is** the configuration — no separate `config.yaml` needed.

```
# Build the OpenCode tested-phase image
docker build -t silverquillm-opencode-tested:latest docker/opencode-tested/

# Build the OpenCode blind-phase image
docker build -t silverquillm-opencode-blind:latest docker/opencode-blind/
```

### Run

```
# Smoke test — run a small subset to verify the image works
silverquillm smoke --image silverquillm-opencode-tested:latest

# Full run with timeout (all cards, ~2 hours)
silverquillm run --image silverquillm-opencode-tested:latest --timeout 7200
```

Evaluation happens automatically at the end of each run. Results are written to the workspace results directory.

---

## Evaluation Dimensions

Implementations are evaluated across three dimensions:

| Dimension | What It Measures |
| --- | --- |
| **SOS Card Correctness** | Does the agent's card implementation match the card spec? Tested via audited gold-standard tests. |
| **FDN Regression** | Did the agent break any existing Foundations card implementations? All FDN tests re-run after each card. |
| **Engine Regression** | Did the agent break core engine behavior? Full engine test suite re-run after each card. |

---

## Docker Container Flow

The benchmark uses Docker containers instead of pluggable adapters. Each container:

1. Receives card specs and engine context via volume mounts
2. Runs the agent tool (OpenCode, Claude Code, etc.) inside the container
3. Writes implementation artifacts to a shared output volume
4. Emits progress events to `progress.jsonl` for the host runner to monitor

---

## Scoring

Implementations are scored across three evaluation dimensions, weighted by card complexity tier:

| Dimension | What It Measures |
| --- | --- |
| **SOS Card Correctness** | Does the agent's card implementation pass audited gold-standard tests? |
| **FDN Regression** | Did the agent break any existing Foundations card implementations? |
| **Engine Regression** | Did the agent break core engine behavior? |

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
├── status.json                  # Run status & metadata
├── run_summary.json             # Aggregate stats & scoring
├── progress.jsonl               # Real-time progress events
├── stdout.log                   # Container stdout capture
├── stderr.log                   # Container stderr capture
├── engine_diff.patch            # Cumulative engine changes
└── cards/
    └── <card_num>/
        ├── card_impl.py         # Agent's card implementation
        └── result.json          # Per-card eval results
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
