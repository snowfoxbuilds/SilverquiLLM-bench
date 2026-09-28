# PROJECT_MAP.md — Directory Layout

```
AGENTS.md          — Workspace orientation and rules
PROJECT_MAP.md     — This file; directory summary
RULEBOOK.txt       — The entire MTG comprehensive rules. Grep — do not read whole.
pytest.ini         — Pytest configuration for the workspace
conftest.py        — Pytest fixtures shared across the workspace
test_utils.py      — Shared test helpers (`create_game`, `set_board_state`, `put_on_battlefield`, `cast_spell`, …) built on the intent-based DeterministicPlayer.
test_utils.md      — API reference for `test_utils.py` (Player Query / Intent test API)
.gitignore         — Git ignore rules
engine/            — Canonical game engine source. Imported as `engine`.
                     Choice layer: `decisions.py` (Player Decisions, Game Symbols
                     vocabulary, `satisfies`), `queries.py` (Player Query / Answer
                     + boundary validation), `refs_registry.py` (Game Refs),
                     `player.py` (`Player.answer`), `intent_player.py`
                     (`DeterministicPlayer`, `Intent`, transcript).
engine_tests/      — Engine tests (do not modify).
cards/             — Card implementations.
  cards/fdn/       — Completed FDN reference cards (do not modify their tests).
  cards/hob/       — Five selected HOB target-card stubs and detailed instructions.
skills/            — Workspace-local skills (e.g. `grep-rulebook/SKILL.md`).
```

## Card paths

For a HOB card with collector number `N`:

```
cards/hob/hob_<N>/card_spec.json   — card metadata (name, mana_cost, oracle_text, P/T, keywords, …)
cards/hob/hob_<N>/card_impl.py     — implementation stub you complete
cards/hob/hob_<N>/tests.py         — your tests for this card (you create this)
```

For an FDN reference card:

```
cards/fdn/fdn_<N>/card_spec.json   — card metadata
cards/fdn/fdn_<N>/card_impl.py     — completed reference implementation (read for examples)
cards/fdn/fdn_<N>/tests.py         — present for many reference cards (see below); read as test examples
```

### FDN cards that ship with a `tests.py`

There is no hand-maintained list; the tree is the source of truth. Discover the current set at any time with:

```bash
find cards/fdn -mindepth 2 -maxdepth 2 -name tests.py -printf '%h\n' | sort -V
```

As of the latest workspace stage, 86 FDN reference cards ship a `tests.py`. Re-run the `find` command rather than trusting this count. These files are examples and cover only part of the existing cards' behavior.

## Imports

The workspace root is on `sys.path`, so use bare package imports:

```python
from cards.hob.hob_<N>.card_impl import <ClassName>
from engine.card import CardImpl, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from engine.intent_player import Intent
from engine.decisions import Decision, GameRef, DecisionKind
from test_utils import create_game, set_board_state, put_on_battlefield, cast_spell
```
