# AGENTS.md — Workspace Orientation

## Task

Read `instructions.md` and each target card's `card_spec.json` before implementing.

You are implementing FRA and HOB card implementations. Each card's implementation class
must be placed in its assigned file under the FRA and HOB target-card tree at `cards/fra/` and `cards/hob/`:

```
cards/{set_code}/{card_id}/card_impl.py
```

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
- **Predefined classes.** Every card, every face of a card, and every printed
  ability has a predefined, behavior-free class: one class per face and one
  `<ClassName>Ability<N>` class per printed line of text, numbered in printed
  order. Tokens that FRA keyword actions create have theirs in
  `cards/fra/tokens.py`. Every OBJECT, ABILITY and MODE option the engine offers
  carries the predefined class it stands for in its `printed` attr: a copy
  stands for what it copies, and an ability an effect grants stands for the
  printed ability whose text defines it.
- **Illegal choices.** The engine may offer a choice the rules forbid, but it
  must never let one take effect: it rejects it by raising
  `InvalidPlayerChoiceError` (`engine.decisions`), rolls the game back to the
  start of the action and asks again.
- **Question context.** Any Player Query may carry an optional `question`
  annotation telling the player what it asks for when several valid questions
  are possible in one situation (`CardType.ARTIFACT` on "choose an artifact
  card"). An engine need not attach one; when it does, its values are canonical
  — Game Symbols, predefined classes, Game Refs, or Player Decisions built from
  them — and a string or custom symbol is rejected with `MalformedAttrsError`.

Tests drive play with action scripts and answer every other choice with
**Intents**, and identify cards by their predefined classes, never by name
(see `test_utils.md`).

## Rules

1. **Card location** — Each card's implementation stays in
   `cards/{set_code}/{card_id}/card_impl.py`, and the predefined classes its stub
   declares keep their names. Do not move or rename card directories. Your own
   FRA and HOB tests belong at `cards/{set_code}/{set_code}_<N>/tests.py`.

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
- Per-card FRA and HOB tests you write at `cards/{set_code}/{set_code}_{collector_number}/tests.py`.

The workspace `pytest.ini` configures `python_files = test_*.py tests.py` for
discovery of all three patterns and sets a per-test timeout (5 minutes).

Standard imports inside per-card tests:

```python
from cards.fra.fra_<N>.card_impl import <ClassName>, <ClassName>Ability1
from cards.hob.hob_<N>.card_impl import <ClassName>
from engine.card import Creature, Instant                  # or whichever base
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import Intent
from engine.decisions import Decision, GameRef, DecisionKind
from test_utils import create_game, set_board_state, put_on_battlefield, cast_spell
from test_utils import act, act_illegal, script, run_scripts, resolve_stack
```

## Rules questions → grep RULEBOOK.txt

`RULEBOOK.txt` (workspace root) is the Magic: The Gathering Comprehensive Rules — the authoritative source for any rules question. **Whenever you're unsure how a mechanic works (keyword behavior, timing, replacement vs trigger ordering, state-based actions, etc.), check the rulebook before guessing in a `card_impl.py` or an `engine/` change.**

The file is large — don't `cat` or `Read` it whole. See the workspace skill at [`skills/grep-rulebook/SKILL.md`](skills/grep-rulebook/SKILL.md) for grep recipes, the file's structure (numbered rules + glossary), and best practices.

## Tools

Git is available. The workspace is initialized as a git repository at stage time.

## Navigation

See `PROJECT_MAP.md` for the directory layout.
