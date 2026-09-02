# AGENTS.md — Workspace Orientation

## Task

You are implementing the smoke benchmark's target cards: a few FDN cards whose
implementations have been reduced to stubs. `prompt.md` names the exact
targets; each one's implementation class lives in its stub file:

```
cards/fdn/fdn_<N>/card_impl.py
```

Every other card under `cards/fdn/` is a completed reference implementation —
read them for examples.

Card choices go through the **Player Query / Player Decision** protocol: an
implementation that needs a choice raises a Player Query through the engine's
query machinery (it never calls a player `choose_*` method — there is none).
Tests answer those queries with **Intents** (see `test_utils.md`).

## Hard Rules

1. **Card location invariant** — Each target card's canonical implementation
   class must remain in `cards/fdn/fdn_<N>/card_impl.py`, keeping the class
   name the stub pins. Do not move or rename card directories.

2. **Staged-test integrity** — Treat `engine_tests/` as read-only: do not
   modify, add to, or delete files in it. Likewise do not modify or delete any
   existing FDN reference test file at `cards/fdn/fdn_*/tests.py` (you may read
   them as examples, but never edit them). These staged tests are local
   feedback only; grading runs the harness's own authoritative suites outside
   this workspace. Editing them — including adding new files — cannot change
   your score, it will only mislead you about whether your engine changes are
   correct. Your own tests for a target card belong at
   `cards/fdn/fdn_<N>/tests.py` (the targets ship without one).

3. **Engine envelope: modify freely; the audited tests are the judge** — You
   may add, change, rename, move, refactor, or delete anything inside
   `engine/`. There is no additive-only rule and no diff policing: your engine
   diff is recorded as a diagnostic, never scored. The entire judgment is the
   three audited dimensions run against your final `engine/` — target-card
   correctness, FDN card regression, engine regression — so a change that
   breaks behavior or public symbols the audited tests rely on (for example
   `engine.card.CardImpl`, `engine.game`, the Player Query machinery) simply
   shows up as failing tests. That scoring is the only enforcement. The staged
   tests are local feedback, not the grader: `engine_tests/` is your local
   proxy for the Engine Regression dimension, and the colocated FDN
   `cards/fdn/fdn_*/tests.py` files give illustrative local regression
   coverage. Authoritative evaluation runs outside this workspace against the
   harvested engine, using its own audited FDN suite — broader than the staged
   files, and not required to match them. Keeping the staged tests green is
   useful evidence, not a guarantee that the audited FDN regression dimension
   is green.

4. **Life mutation goes through `gain_life` / `lose_life`** — A card
   implementation must change a player's life **only** by calling
   `engine.game.gain_life(game, player, amount)` or
   `engine.game.lose_life(game, player, amount)`. Never assign `player.life`
   directly (`player.life += …` / `-= …`). These helpers fire
   `GainsLifeTriggeredEvent` / `LosesLifeTriggeredEvent`, so life-triggered
   abilities (Ajani's Pridemate, "whenever you lose life", drains) fire on
   their own — do not hand-roll those events either. Combat/spell *damage* is
   separate (it already fires `LosesLifeTriggeredEvent` from `deal_damage`); a
   life *payment* as a cost routes through `lose_life`. Direct `.life` mutation
   in a card impl is rejected by the AST guard
   (`engine_tests/test_card_impl_ast_guard.py`, rule (d)).

5. **Own enters-triggers fire on their own entry (rule 603.3a)** — The engine
   registers an entering permanent's own triggers **before** firing its
   `EntersBattlefieldTriggeredEvent` (in `move_to_zone` and `create_token`), so
   a "when this creature/permanent enters" ability registered in
   `register_triggers` fires on the source's own entry — implement it as a
   normal self-matching ETB trigger (`condition` returns `event.permanent is
   source`). Do **not** add an `on_resolve` self-mint workaround for it (that
   double-fires now). An ability that reads "whenever **another** … enters"
   must exclude the source in its own condition filter (`if permanent is
   source: return False`); the engine no longer suppresses the whole event.

6. **Counters are an engine primitive** — Add/remove counters only through
   `engine.game.add_counter(game, permanent, type, amount)` /
   `remove_counter(...)`, and read them via `permanent.counters` (or
   `_generic_counters` for named types). Never store counters in a card-private
   attribute (`self.incubation_counters` etc.): it is invisible to state
   comparison and to the replay executor's `CounterAdded` sync. Direct
   `*_counter(s)` attribute writes are rejected by the AST guard
   (`engine_tests/test_card_impl_ast_guard.py`, rule (g)); the engine's own
   `plus_one_counters` / `minus_one_counters` / `_generic_counters` are exempt.

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
  Many FDN cards ship with a `tests.py` — see `PROJECT_MAP.md` for how to
  list them, and use them as illustrative per-card test examples (local
  coverage only; the audited FDN suite the grader runs lives outside this
  workspace).
- Per-card tests you write for the target cards at
  `cards/fdn/fdn_{collector_number}/tests.py`.

The workspace `pytest.ini` configures `python_files = test_*.py tests.py` for
discovery of all three patterns and sets a per-test timeout (5 minutes).

Standard imports inside per-card tests:

```python
from cards.fdn.fdn_<N>.card_impl import <ClassName>
from engine.card import Creature, Instant                  # or whichever base
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from engine.intent_player import Intent
from engine.decisions import Decision, GameRef, DecisionKind
from test_utils import create_game, set_board_state, put_on_battlefield, cast_spell
```

## Engine Extension Scope

- **May**: add, modify, rename, move, refactor, or delete anything inside
  `engine/` — the engine is yours for the run.
- **Judged by**: the three audited dimensions against your final `engine/`.
  Breaking behavior or public symbols the audited tests rely on fails those
  tests; nothing else about the engine is policed or scored.
- **Advice**: prefer generic, reusable extensions over card-specific hacks —
  they are far likelier to keep the FDN and engine regression dimensions green.

## Rules questions → grep RULEBOOK.txt

`RULEBOOK.txt` (workspace root) is the Magic: The Gathering Comprehensive Rules — the authoritative source for any rules question. **Whenever you're unsure how a mechanic works (keyword behavior, timing, replacement vs trigger ordering, state-based actions, etc.), check the rulebook before guessing in a `card_impl.py` or an `engine/` change.**

The file is large — don't `cat` or `Read` it whole. See the workspace skill at [`skills/grep-rulebook/SKILL.md`](skills/grep-rulebook/SKILL.md) for grep recipes, the file's structure (numbered rules + glossary), and best practices.

## Tools

Git is available. The workspace is initialized as a git repository at stage time.

## Navigation

See `PROJECT_MAP.md` for the directory layout.
