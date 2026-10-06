# AGENTS.md — Workspace Orientation

## Task

You are implementing three FDN cards whose implementations have been reduced
to stubs. The targets are exactly these files (the task prompt restates them):

```
cards/fdn/fdn_129/card_impl.py   — Leyline Axe
cards/fdn/fdn_205/card_impl.py   — Seismic Rupture
cards/fdn/fdn_232/card_impl.py   — Scavenging Ooze
```

These three implementations are the writable targets. Every other `cards/fdn/`
implementation is a completed reference (read them for examples).

The engine may have deficiencies and bugs, and so may the existing tests. It's your job to make sure your
implementations behave correctly according to the rules in `RULEBOOK.txt`, and
that your changes don't break existing cards.

Every choice a player makes goes through the **Player Query / Player
Decision** protocol: the engine offers the options and the player picks
among them. An implementation that needs a choice raises a Player Query
through the engine's query machinery (it never calls a player `choose_*`
method — there is none).

- **This is how the game runs.** When a player receives priority, the engine
  raises a **Priority Query** offering the choices a real player could make at
  that moment: casting a spell or playing a land is an OBJECT option, activating
  an ability (mana and loyalty abilities included) is an ABILITY option, and
  declining passes priority. The engine carries out the chosen action.
  Declaring attackers and blockers are Player Queries too.
- **Predefined classes.** Every card and every printed ability has a predefined,
  behavior-free class: the card's class and one `<ClassName>Ability<N>` class
  per printed line of text, numbered in printed order. Every OBJECT, ABILITY and
  MODE option the engine offers carries the predefined class it stands for in
  its `printed` attr.
- **Illegal choices.** The engine may offer a choice the rules forbid, but it
  must never let one take effect: it rejects it by raising
  `InvalidPlayerChoiceError` (`engine.decisions`), rolls the game back to the
  start of the action and asks again.

Tests drive play with action scripts and answer every other choice with
**Intents**, and identify cards by their predefined classes, never by name
(see `test_utils.md`).

## Rules

1. **Card location** — Each target card's implementation class stays in its
   stub file (`cards/fdn/fdn_129/card_impl.py`, `cards/fdn/fdn_205/card_impl.py`,
   `cards/fdn/fdn_232/card_impl.py`), under the class name the stub gives. Do
   not move or rename card directories, or rename the predefined classes the
   stub declares. Your own tests for a target card belong at
   `cards/fdn/fdn_<N>/tests.py` (the targets ship without one).

2. **The engine is yours to change** — You may add, change, rename, move,
   refactor, or delete anything inside `engine/`. Prefer generic, reusable
   extensions over card-specific hacks. Existing cards and engine behavior must
   keep working, including public names such as `engine.card.CardImpl`,
   `engine.game` and the Player Query machinery, and the engine surface
   `test_interface.md` names. `test_interface.py` and `test_interface.md`
   are fixed: do not change them.

3. **Life changes go through `gain_life` / `lose_life`** — A card
   implementation changes a player's life **only** by calling
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

4. **Own enters-triggers fire on their own entry (rule 603.3a)** — The engine
   registers an entering permanent's own triggers **before** firing its
   `EntersBattlefieldTriggeredEvent` (in `move_to_zone` and `create_token`), so
   a "when this creature/permanent enters" ability registered in
   `register_triggers` fires on the source's own entry — implement it as a
   normal self-matching ETB trigger (`condition` returns `event.permanent is
   source`). Do **not** add an `on_resolve` self-mint workaround for it (that
   double-fires). An ability that reads "whenever **another** … enters" must
   exclude the source in its own condition filter (`if permanent is source:
   return False`).

5. **Counters are an engine primitive** — Add/remove counters only through
   `engine.game.add_counter(game, permanent, type, amount)` /
   `remove_counter(...)`, and read them via `permanent.counters` (or
   `_generic_counters` for named types). Never store counters in a card-private
   attribute (`self.incubation_counters` etc.): the engine and other cards
   cannot see it. Direct `*_counter(s)` attribute writes are rejected by the
   AST guard (`engine_tests/test_card_impl_ast_guard.py`, rule (g)); the
   engine's own `plus_one_counters` / `minus_one_counters` /
   `_generic_counters` are exempt.

## Test Commands

Run from the workspace root:

```bash
python3 -m pytest
```

This discovers:
- Engine tests at `engine_tests/test_*.py`.
- Per-card FDN tests at `cards/fdn/fdn_{collector_number}/tests.py`. Many FDN
  cards ship with a `tests.py` — see `PROJECT_MAP.md` for how to list them, and
  use them as per-card test examples. They cover only part of the existing
  cards' behavior.
- Per-card tests you write for the target cards at
  `cards/fdn/fdn_{collector_number}/tests.py`.

The workspace `pytest.ini` configures `python_files = test_*.py tests.py` for
discovery of all three patterns and sets a per-test timeout (5 minutes).

Standard imports inside per-card tests:

```python
from cards.fdn.fdn_<N>.card_impl import <ClassName>
from engine.card import Creature, Instant                  # or whichever base
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import Intent
from engine.decisions import Decision, GameRef, DecisionKind
from test_utils import create_game, set_board_state, put_on_battlefield, cast_spell
from test_utils import act, act_illegal, script, run_scripts, resolve_stack, source_pattern
```

## Rules questions → grep RULEBOOK.txt

`RULEBOOK.txt` (workspace root) is the Magic: The Gathering Comprehensive Rules — the authoritative source for any rules question. **Whenever you're unsure how a mechanic works (keyword behavior, timing, replacement vs trigger ordering, state-based actions, etc.), check the rulebook before guessing in a `card_impl.py` or an `engine/` change.**

The file is large — don't `cat` or `Read` it whole. See the workspace skill at [`skills/grep-rulebook/SKILL.md`](skills/grep-rulebook/SKILL.md) for grep recipes, the file's structure (numbered rules + glossary), and best practices.

## Tools

Git is available. The workspace is initialized as a git repository at stage time.

## Navigation

See `PROJECT_MAP.md` for the directory layout.
