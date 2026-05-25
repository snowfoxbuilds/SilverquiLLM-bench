# PROJECT_MAP.md — Directory Layout

```
AGENTS.md          — Workspace orientation and rules
PROJECT_MAP.md     — This file; directory summary
RULEBOOK.txt       — The entire MTG comprehensive rules. Grep — do not read whole.
prompt.md          — Per-run task prompt (written at stage time)
run_manifest.json  — Per-run manifest (benchmark set, card filter, timeout, deadline)
pytest.ini         — Pytest configuration for the workspace
conftest.py        — Pytest fixtures shared across the workspace
test_utils.py      — Shared test helpers (`create_game`, `set_board_state`, …)
test_utils.md      — API reference for `test_utils.py`
.gitignore         — Git ignore rules
engine/            — Canonical game engine source. Imported as `engine`.
engine_tests/      — Engine regression tests (do not modify).
cards/             — Card implementations.
  cards/fdn/       — Completed FDN reference cards (do not modify their tests).
  cards/sos/       — SOS card stubs to implement.
skills/            — Workspace-local skills (e.g. `grep-rulebook/SKILL.md`).
```

## Card paths

For an SOS card with collector number `N`:

```
cards/sos/sos_<N>/card_spec.json   — card metadata (name, mana_cost, oracle_text, P/T, keywords, …)
cards/sos/sos_<N>/card_impl.py     — implementation stub you complete
cards/sos/sos_<N>/tests.py         — your tests for this card (you create this)
```

For an FDN reference card:

```
cards/fdn/fdn_<N>/card_spec.json   — card metadata
cards/fdn/fdn_<N>/card_impl.py     — completed reference implementation (read for examples)
cards/fdn/fdn_<N>/tests.py         — only present for the cards listed below; read as test examples
```

### FDN cards that ship with a `tests.py`

This is the canonical list — agent prompts refer back here instead of duplicating it.
Discover the current set at any time with:

```bash
find cards/fdn -mindepth 2 -maxdepth 2 -name tests.py -printf '%h\n' | sort -V
```

As of the latest workspace stage, the list is: `fdn_13`, `fdn_142`, `fdn_205`, `fdn_215`, `fdn_244`. If you suspect the list has grown, re-run the `find` command above — it is authoritative.

## Imports

The workspace root is on `sys.path`, so use bare package imports:

```python
from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import CardImpl, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state
```
