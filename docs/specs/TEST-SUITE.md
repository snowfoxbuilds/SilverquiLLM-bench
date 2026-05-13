Status: SETTLED

Last updated: 2026-04-28

# Test Suite

Agents write their own tests. In v1, agent tests are harvested as artifacts; scoring uses audited tests only. Test quality scoring and cross-evaluation are v2 features (see Test Harvester).

## Context

Unlike traditional benchmarks with pre-built test suites, SilverquiLLM-bench has agents generate tests as part of the benchmark. In v1, only audited tests are used for scoring. Agent-written tests are harvested for future promotion to the audited suite via a test harvester pipeline.

## Design

### Evaluation Architecture

**Implementation Phase** (per agent):

The agent receives the full SOS card set in a Docker container with FDN cards as examples. Depending on the configured mode:

1. **Blind mode** — Agent implements all cards without writing or running tests.
2. **Tested mode** — Agent implements cards and writes tests, iterating at its own discretion.
Both modes produce `card_impl.py` per card. Tested mode also produces `tests.py` per card.

**Evaluation Phase** (after all agents finish):

1. **SOS Card Correctness** — Audited SOS tests against each agent's `card_impl.py` + agent's `engine_work/`
2. **FDN Card Regression** — Audited FDN tests against pre-filled FDN impls + agent's `engine_work/`
3. **Engine Regression** — Core engine tests against agent's `engine_work/`
Self-eval and cross-eval deferred to v2 (requires test harvester). Agent-written `tests.py` files are harvested as artifacts but not used for v1 scoring.

### Test Harvester (v2)

Agent-written `tests.py` files are harvested as artifacts from each run but not scored in v1. A future **test harvester** pipeline will:

1. **Collect** — Gather all agents' `tests.py` files across runs for each SOS card
2. **Validate** — Run each agent's tests against all agents' implementations to check correctness (tests that fail against all implementations are likely buggy)
3. **Deduplicate** — Identify redundant tests across agents (same behavior, different code)
4. **Score** — Measure test quality: discrimination (do tests differentiate good from bad impls?), difficulty calibration (passed by some but not all agents), coverage (behaviors tested)
5. **Promote** — Move validated, high-quality agent tests into `tests/audited/sos/` to strengthen the audited suite
This enables cross-eval (N×N matrix), self-eval, and test quality scoring as future evaluation dimensions. See [SCORING.md](http://scoring.md/) → Future Work.

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
├── card_impl.py              # Agent's implementation
├── tests.py                  # Agent's tests (tested mode only)
└── result.json               # Per-card evaluation results
```

### Replay Validation (Engine Correctness)

Engine correctness is validated by replaying recorded MTGA game data (sourced from 17lands) through the Python engine and verifying game-state checkpoints match recorded outcomes. This replaces the originally planned XMage differential testing — Replay Validation is more valuable because MTGA is WotC's own rules implementation, and cross-language Java↔Python comparison adds complexity without confidence.

The Replay Validation pipeline is built after all FDN 001–291 cards are implemented. First benchmark runs proceed without it as Pipeline Validation Runs.

## Decisions

- **Agents write their own tests**: Test quality is part of evaluation, not pre-built. [SETTLED]
- **test_utils required**: Guarantees consistent format for cross-evaluation. [SETTLED]
- **30 tests per card cap**: Prevents gaming via trivial test spam. [SETTLED]
- **Audited-only evaluation for v1**: Self-eval and cross-eval deferred to v2 (requires test harvester). v1 runs audited tests only across three dimensions. [UPDATED]
- **Audited tests are LLM-drafted, failure-reviewed**: Initial audited suites are generated by LLM agents, then failures during benchmark runs are reviewed and corrected by a human. Passing tests are accepted as-is. Test Audit Web Tool remains a future option for deeper curation. [SETTLED]
- **Audited test structure: per-card files**: `tests/audited/{set_code}/{collector_number}/tests.py`, importing from `card_impl`. Uniform structure across all sets for reuse. Evaluator swaps in any agent's implementation as `card_impl.py`. [SETTLED]
- **Unified test path**: All card tests (FDN and SOS) live under `tests/audited/{set_code}/{collector_number}/tests.py`. Former `tests/cards/` FDN tests merged into `tests/audited/fdn/`. One structure, one evaluator. [UPDATED]
- **FDN tests as regression suite**: FDN audited tests (`tests/audited/fdn/`) serve as the post-run regression check against the agent's Writable Engine. [SETTLED]
