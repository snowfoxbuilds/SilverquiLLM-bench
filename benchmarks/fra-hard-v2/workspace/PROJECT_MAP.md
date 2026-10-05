# PROJECT_MAP.md — Directory Layout

```
AGENTS.md          — Workspace orientation and rules
instructions.md    — The implementation task
PROJECT_MAP.md     — This file; directory summary
RULEBOOK.txt       — The entire MTG comprehensive rules. Grep — do not read whole.
pytest.ini         — Pytest configuration for the workspace
conftest.py        — Pytest fixtures shared across the workspace
test_utils.py      — Shared test helpers (`create_game`, `script`, `run_scripts`, `cast_spell`, …) built on the Test Interface's scripted player.
test_utils.md      — API reference for `test_utils.py` (Priority Query, action script and Intent test API)
test_interface.py  — The Test Interface (fixed; see test_interface.md)
engine/            — Canonical game engine source. Imported as `engine`.
                     Choice layer: `decisions.py` (Player Decisions, Game Symbols
                     vocabulary, `satisfies`, `InvalidPlayerChoiceError`),
                     `queries.py` (Player Query / Answer + boundary validation),
                     `refs_registry.py` (Game Refs), `player.py`
                     (`Player.answer`).
                     Priority: `priority.py` (the Priority Query and the actions
                     it offers), `attempts.py` / `rollback.py` (rejecting an
                     illegal choice and rolling the game back).
engine_tests/      — Engine tests.
cards/             — Card implementations.
  cards/fdn/       — Completed FDN reference cards; `tokens.py` holds the FDN tokens.
  cards/fra/       — The five FRA targets, and `tokens.py` with the predefined
                     classes of the tokens FRA keyword actions create.
  cards/hob/       — The five HOB targets.
skills/            — Workspace-local skills (e.g. `grep-rulebook/SKILL.md`).
```

## Card paths

For each target card:

```
cards/{set_code}/{set_code}_<N>/card_spec.json   — the complete card specification; card_faces describes every face
cards/{set_code}/{set_code}_<N>/card_impl.py     — stub you complete, with the card's predefined classes
cards/{set_code}/{set_code}_<N>/tests.py         — your tests for this card (you create this)
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

These files are examples and cover only part of the existing cards' behavior.

## Imports

The workspace root is on `sys.path`, so use bare package imports:

```python
from cards.fra.fra_<N>.card_impl import <ClassName>
from cards.hob.hob_<N>.card_impl import <ClassName>
from engine.card import CardImpl, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import Intent
from engine.decisions import Decision, GameRef, DecisionKind
from test_utils import create_game, set_board_state, put_on_battlefield, cast_spell
from test_utils import act, script, run_scripts, resolve_stack
```
