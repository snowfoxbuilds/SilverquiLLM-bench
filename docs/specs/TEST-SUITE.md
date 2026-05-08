Status: SETTLED

Last updated: 2026-04-28

# Test Suite

Agents write their own tests. Test quality is part of the evaluation.

## Context

Unlike traditional benchmarks with pre-built test suites, SilverquiLLM-bench has agents generate tests as part of the benchmark. This enables cross-evaluation and measures test-writing ability as a separate dimension.

## Design

### Evaluation Architecture

**Implementation Phase** (per card per agent):

1. **Blind implementation** — Agent writes card code with no tests. Saved as `blind_impl.py`.
2. **Test-informed implementation** — Agent writes tests + updates code (max 3 rounds). Saved as `tested_impl.py` + `tests.py`.
**Evaluation Phase** (after all agents finish):

1. **Self-eval** — Each agent's code against its own tests
2. **Cross-eval** — Each agent's code against every other agent's tests (N×N matrix)
3. **Audited eval** — All code against human-curated gold-standard tests
### Cross-Evaluation Matrix

With N agents, each cell is a per-card pass rate:

| Code ↓  Tests → | Agent A | Agent B | Agent C | Audited |
| --- | --- | --- | --- | --- |
| Agent A blind | self | cross | cross | gold |
| Agent A tested | self | cross | cross | gold |
| Agent B blind | cross | self | cross | gold |
| Agent B tested | cross | self | cross | gold |
| Agent C blind | cross | cross | self | gold |
| Agent C tested | cross | cross | self | gold |

Matrix reveals: implementation quality (row pass rates), test quality (column discrimination), self-serving bias (diagonal vs off-diagonal), blind vs tested delta.

### Test Constraints

- Tests **must** use `test_utils` helpers (`create_game`, `set_board_state`, `cast_spell`, etc.)
- Maximum **30 tests per card** (first 30 kept if exceeded)
- Tests import from standardized `card_impl` path for cross-evaluation compatibility
- Each test tagged with a category: `basic`, `ability`, `edge`, `interaction`, `rules`
### Test Structure

```python
import pytest
from silverquillm.test_utils import (
    create_game, set_board_state, cast_spell,
    advance_to_phase, assert_zone_contains,
    assert_life_total, assert_battlefield_count,
)

class TestCardName:
    def test_basic_cast(self):
        game = create_game()
        # setup + assertions

    def test_core_ability(self):
        game = create_game()
        # setup + assertions
```

### Test Utilities API

```python
def create_game(player1_life=20, player2_life=20, seed=None) -> GameState: ...
def set_board_state(game, player, battlefield=[], hand=[], graveyard=[], mana_pool="", life=None) -> None: ...
def cast_spell(game, player, card_name, targets=None, choices=None) -> None: ...
def advance_to_phase(game, phase) -> None: ...
def declare_attackers(game, attackers) -> None: ...
def declare_blockers(game, blocks) -> None: ...
```

### Test Quality Guidelines

- Each test tests one thing
- Tests are independent (no shared state)
- Tests are deterministic (seeded randomness)
- Board state setup is minimal
- Assertions are specific (`assert_zone_contains(...)` not `assert len(...) == 1`)
### Test Count Expectations

| Card Complexity | Tests |
| --- | --- |
| Vanilla creatures / basic lands | 2-3 |
| Simple abilities | 5-8 |
| Complex cards | 10-20 |
| Planeswalkers | 15-25 |
| Full set (~250-300 cards) | ~2,000-4,000 total |

### Artifacts Per Card

Artifacts are scoped per run (one run = one agent/model). Layout matches [BENCHMARK-RUNNER.md](http://benchmark-runner.md/):

```javascript
results/{run_name}/cards/{card_id}/
├── blind_impl.py
├── tested_impl.py
├── tests.py
├── result.json
├── postmortem.jsonl
├── agent_thoughts.md
├── iterations/
│   ├── round_1/ (impl.py + tests.py + pytest_output.txt)
│   └── round_2/ ...
└── audited_tests.py          # Gold-standard tests (if audited)
```

### Test Audit Web Tool

Web interface for human reviewers to:

- Browse all agents' test suites side by side per card
- Flag tests as: correct, incorrect, weak, duplicate
- Select best tests across agents into audited suite
- Add manual tests for uncovered gaps
- Export curated suite for final evaluation
### Replay Validation (Engine Correctness)

Engine correctness is validated by replaying recorded MTGA game data (sourced from 17lands) through the Python engine and verifying game-state checkpoints match recorded outcomes. This replaces the originally planned XMage differential testing — Replay Validation is more valuable because MTGA is WotC's own rules implementation, and cross-language Java↔Python comparison adds complexity without confidence.

The Replay Validation pipeline is built after all FDN 001–291 cards are implemented. First benchmark runs proceed without it as Pipeline Validation Runs.

## Decisions

- **Agents write their own tests**: Test quality is part of evaluation, not pre-built. [SETTLED]
- **test_utils required**: Guarantees consistent format for cross-evaluation. [SETTLED]
- **30 tests per card cap**: Prevents gaming via trivial test spam. [SETTLED]
- **Three-layer evaluation (self/cross/audited)**: Self-eval alone is unreliable; cross-eval removes bias; audited is authoritative. [SETTLED]
