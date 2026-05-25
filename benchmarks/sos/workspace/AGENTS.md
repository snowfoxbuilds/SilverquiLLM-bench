# AGENTS.md — Workspace Orientation

## Task

You are implementing SOS card implementations. Each card's implementation class
must be placed in its assigned file:

```
cards/sos/{card_id}/card_impl.py
```

## Hard Rules

1. **Card location invariant** — Each card's canonical implementation class must
   remain in `cards/sos/{card_id}/card_impl.py`. Do not move or rename card
   directories.

2. **Staged-test integrity** — Do not modify any files under `engine_tests/` or
   any existing FDN reference test files at `cards/fdn/fdn_*/tests.py`. These
   tests are for your local verification and learning only; the runner uses its
   own authoritative copies for grading. Modifying these tests will not change
   your score — it will only mislead you about whether your engine changes are
   correct.

3. **Additive-only engine modifications** — You may add new methods, classes,
   helpers, and files inside `engine/`. You may modify the bodies of existing
   functions to implement card behavior. You MUST NOT rename, move, or delete
   anything that already exists in `engine/` — no renaming, no refactoring.
   Restructuring the engine will break the grader's imports and zero your score.

These rules are derived from the project's Workspace Contract decisions
(maintained outside this workspace). They ensure deterministic grading.

## Test Commands

Run from the workspace root:

```bash
pytest
```

This discovers:
- Engine regression tests at `engine_tests/test_*.py`.
- Per-card FDN reference tests at `cards/fdn/fdn_{collector_number}/tests.py`.
  Only a handful of FDN cards ship with a `tests.py` (currently `fdn_13`,
  `fdn_142`, `fdn_205`, `fdn_215`, `fdn_244`) — use them as illustrative
  per-card test examples when present.
- Per-card SOS tests you write at `cards/sos/sos_{collector_number}/tests.py`.

The workspace `pytest.ini` configures `python_files = test_*.py tests.py` for
discovery of all three patterns and sets a per-test timeout (5 minutes).

Standard imports inside per-card tests:

```python
from cards.sos.sos_<N>.card_impl import <ClassName>
from engine.card import Creature, Instant            # or whichever base
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state
```

## Engine Extension Scope

- **May**: Add files, methods, classes, and helpers inside `engine/`.
- **May**: Modify the bodies of existing functions in `engine/`.
- **Must NOT**: Rename, move, or delete anything existing in `engine/`.

## Rules questions → grep RULEBOOK.txt

`RULEBOOK.txt` (workspace root) is the Magic: The Gathering Comprehensive Rules — the authoritative source for any rules question. **Whenever you're unsure how a mechanic works (keyword behavior, timing, replacement vs trigger ordering, state-based actions, etc.), check the rulebook before guessing in a `card_impl.py` or an `engine/` change.**

The file is large — don't `cat` or `Read` it whole. See the workspace skill at [`skills/grep-rulebook/SKILL.md`](skills/grep-rulebook/SKILL.md) for grep recipes, the file's structure (numbered rules + glossary), and best practices.

## Tools

Git is available. The workspace is initialized as a git repository at stage time.

## Navigation

See `PROJECT_MAP.md` for the directory layout.
