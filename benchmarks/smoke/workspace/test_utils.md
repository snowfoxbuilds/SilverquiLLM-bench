# Test Utilities API Reference

Helper functions for writing card tests. Import from `test_utils`.

## How the game runs

Every choice a player makes is a **Player Query** answered with a **Player
Decision**: the engine offers the options, and the player picks among them.

- **Priority.** When a player receives priority, the engine raises a
  **Priority Query** offering every action that player may begin right now —
  the choices a player would see in a game client. Casting a spell or playing a
  land is an OBJECT option for the card; activating an ability (mana and
  loyalty abilities included) is an ABILITY option. Declining passes priority.
  The engine, not the test, carries out the chosen action.
- **Combat.** Declaring attackers and declaring blockers are Player Queries
  too: the player chooses the creatures that attack or block, and then what
  each attacks or blocks.
- **Choices along the way.** Targets, modes, X, payment, sacrifices and other
  choices raised while an action is taken or an object resolves are Player
  Queries as well.
- **Predefined classes.** Every card and every printed ability has a predefined
  class: the card's class (`LlanowarElves`) and one class per printed line of
  text, numbered in printed order (`LlanowarElvesAbility1`; keywords sharing a
  line are separate abilities, and modes count as abilities). Every OBJECT,
  ABILITY and MODE option carries the class it stands for in its `printed`
  attr, so `Decision.obj(printed=LlanowarElves)` picks the card whatever object
  the engine presents.
- **Illegal choices.** An engine may offer a choice the rules forbid, but it
  must not let it take effect: it rejects it by raising
  `engine.decisions.InvalidPlayerChoiceError`, rolls the game back to the start
  of the action (or of the choice, while an object resolves) and asks again.
- **No name strings.** Tests place, choose and assert by predefined class or by
  object, never by a card's name. A helper given a name string raises
  `TestSetupError`.

The intent-based `DeterministicPlayer` answers every query: Priority Queries
and combat declarations from the player's **action script**, everything else
through **Intents**.

## Board setup

### `create_game`

`create_game(deck1=None, deck2=None, *, player1_life=20, player2_life=20) -> GameState`

Create a two-player game with intent-based `DeterministicPlayer` instances. Each
player's `.game` is set so `end_intent` postconditions can read game state.

```python
from test_utils import create_game
game = create_game(player1_life=25)
```

### `set_board_state`

`set_board_state(game, player_index, *, battlefield=None, hand=None, graveyard=None, life=None, mana=None) -> None`

Set zone contents and player state. Only zones explicitly provided are modified.
Each placed object is given a stable engine-minted `instance_id` (for the zone
it is placed in) that a test can reference in a preference.

### `put_on_battlefield`

`put_on_battlefield(game, player, card) -> card`

Place one card on `player`'s battlefield and return it with `card.instance_id`
set — the idiomatic way to obtain an object to target.

```python
from test_utils import create_game, put_on_battlefield
from cards.fdn.fdn_227.card_impl import LlanowarElves

game = create_game()
elves = put_on_battlefield(game, game.players[1], LlanowarElves())
```

## Action scripts

Each player has an ordered action script. Every Priority Query and every
combat declaration the player receives consumes the next entry; a player whose
script is dry passes (and declares no attackers or blockers).

```python
from test_utils import act, act_illegal, branch, pass_priority, script, run_scripts
```

- `act(*preferences, choices=(), goal=None, label="", branches=None, scoped=None)`
  — an action the player must take. Preferences are tried in order; each is a
  Player Decision or a predefined class (a card class stands for
  `Decision.obj(printed=cls)`, an ability or mode class for
  `Decision.ability(printed=cls)` / `Decision.mode(printed=cls)`). The same
  preferences, then `choices`, answer every query raised while the action is
  taken that no Intent claims (targets, modes, X, payment). The test fails
  with `ScriptEntryError` (a `PostconditionError`) if the action is not
  offered, if it is rejected with no branch left to retry it with, or if
  `goal(game)` is falsey once it has taken effect.
- `act_illegal(*preferences, choices=(), label="", branches=None, scoped=None)`
  — an action the rules forbid: it passes if every branch is not offered or
  is rejected, and fails the test if any branch takes effect. Either way the
  same query then goes to the next entry.
- `pass_priority(label="")` — pass this priority window.
- For a combat declaration, an entry's preferences are all the creatures that
  attack or block, and `scoped` maps a creature to what it attacks or blocks:
  `act(wall, scoped={wall: bear})` blocks the bear with the wall.

### Retries are explicit branches

A rejected attempt is retried only in a way the test writes out. One
preference list is one **branch**; `branches=[...]` lists several, each an
ordinary preference list (or `branch(*preferences, choices=..., scoped=...)`
for its own choices and scoped answers) that answers every query of the
attempt. When the engine rejects an attempt with `InvalidPlayerChoiceError`,
the game is rolled back and the attempt is retried with the next branch; a
branch whose action is not offered is skipped. With no branch left, `act`
fails. Entry-level `choices` and `scoped` are appended to every branch, and
passing both positional preferences and `branches` is a `TypeError`.

```python
from cards.fdn.fdn_169.card_impl import BakeIntoAPie
from cards.fdn.fdn_223.card_impl import GiantGrowth

# With only {G} available, Bake into a Pie is offered but rejected as
# unpayable; the second branch then casts Giant Growth.
script(game, 0, act(branches=[[BakeIntoAPie], [GiantGrowth]]))
run_scripts(game)

# One branch is not retried: this fails with ScriptEntryError("rejected"),
# although Giant Growth is preferred too.
script(game, 0, act(BakeIntoAPie, GiantGrowth))
```

A query may carry an optional `question` annotation saying what it asks for
when several questions are possible in one situation — `CardType.ARTIFACT` on
"choose an artifact card", for instance. Engines need not attach one; when
they do, it holds only Game Symbols, predefined classes, Game Refs or Player
Decisions built from them (a string or custom symbol is rejected). A branch's
`per_query` maps keys to the preferences that answer the query a key matches,
on any query: `branch(a, b, per_query={CardType.ARTIFACT: [a], CardType.CREATURE: [b]})`.
A key is an object the annotation holds, matched as preferences match options
(a Player Decision by `satisfies()`, anything else by identity or equality),
or a predicate over the query (`lambda query: ...` reading its options,
source or bounds) to infer the question when there is no annotation. Keys
are tried in order and the first match wins, its list used as given — an
empty one declines an optional choice; a query no key matches,
including one combined question for every type, is answered by the branch's
own preferences. `act`, `act_illegal` and `Intent` take `per_query` too.

### `script` / `run_scripts`

`script(game, player_index, *entries) -> None` — give a player an action
script, replacing any entries left from an earlier one.

`run_scripts(game, *, max_priority=1000) -> None` — play until every script is
consumed, leaving the stack in place. Priority moves as in a real game: a
player who acts keeps priority; two passes in a row resolve the top of the
stack or, on an empty stack, move to the next step that grants priority.

```python
from cards.fdn.fdn_227.card_impl import LlanowarElvesAbility1   # "{T}: Add {G}."

script(game, 0, act(LlanowarElvesAbility1, goal=lambda g: p0.mana_pool.total() == 1))
run_scripts(game)
```

### `resolve_stack`

`resolve_stack(game) -> None` — resolve the entire stack with every player
passing. It consumes no script entries.

### `advance_to_phase` / `advance_game_to_phase`

`advance_to_phase(game, phase, step=None) -> None` — fast-forward without
granting priority; consumes no script entries. It only sets the phase: no
untap, draw, upkeep or end-step events fire.

`advance_game_to_phase(game, phase, step=None) -> None` — drive real phase
transitions to `phase`/`step`: untap, draw, the upkeep, beginning-of-combat and
end-step events, combat damage and cleanup all happen, resolving the stack on
the way. Use it when a test depends on delayed or "at the beginning of" triggers.

## Action helpers

Each helper below is a one-entry `act` script driven through the Priority Query
or combat declaration, so the engine performs the action.

### `cast_spell`

`cast_spell(game, player_index, card, targets=None) -> None`

Find `card` (a predefined class, or the card object) in the player's hand, cast
it, and resolve it. Sets sorcery-speed timing automatically. If `targets` is
given, a transient Intent prefers those objects (by `instance_id`) / players (by
seat) for the target query raised during casting.

### `cast_card`

`cast_card(game, player, card, resolve=True)` — cast a card that is unzoned or
in the caster's hand; the test supplies mana and Intents. Raises `CastingError`
when the cast is not offered or is rejected (rolled back).

### `activate_card_ability` / `activate_loyalty_ability`

`activate_card_ability(game, player, source_card, index=0) -> None`

Activate ability `index` of `card_abilities(source_card)` — the card's
`get_activated_abilities()`, followed by any `get_mana_abilities()` entries not
already listed. Targets are chosen before costs are paid. Raises `AbilityError`
when the ability is not offered or is rejected; nothing is spent then. Resolve
the stack afterwards to run a non-mana ability's effect.

`activate_loyalty_ability(game, player, source_card, index=0)` does the same for
a planeswalker's loyalty abilities.

### `declare_attackers` / `declare_blockers`

`declare_attackers(game, attackers, *, illegal=False) -> None`
`declare_blockers(game, {attacker: [blocker, ...]}, *, illegal=False) -> None`

Advance to the step and declare exactly those creatures, each given as an
object or a predefined class. With `illegal=True` the declaration is one the
rules forbid, scripted as `act_illegal`. When an attacker is blocked by more
than one creature, the engine asks the attacker's controller how to divide its
combat damage, one NUMBER query per blocker; give that player a Baseline Intent
if your test reaches that case.

### More setup and action helpers

- `enter_permanent(game, player, card) -> card` — put `card` into `player`'s hand
  and move it onto the battlefield through the real zone transition, so its
  enters-the-battlefield events and triggers fire.
- `cast_vanilla_spell(game, seat, value=2)` — add mana and cast a generic
  instant costing `{value}`.
- `fund_mana_cost(player, cost)` — add exactly `cost`'s mana to the pool.
- `ability_instance(game, player, source, index=0)` /
  `mana_ability_instance(game, player, source, index=0)` — build a reusable
  `ActivatedAbilityInstance` without activating it.
- `finish_cleanup(game)` — run the cleanup step to completion (discard to hand
  size, state-based actions, triggers).
- `behavioral_game()` / `scenario_game(...)` — a game whose players answer
  unrouted queries with the first offered option (`behavioral_game` also gives
  each player a 40-card library and starts in the precombat main phase).
- `card_colors(card)` — a card's colors derived from its mana cost.

## Intents

```python
from test_utils import Intent
from engine.decisions import Decision, GameRef
from test_utils import source_pattern
```

`Intent(pattern, preferences=(), postcondition=None, branches=(), per_query=())`:

- `pattern: GameRef` — routes a query by matching its source refs (subset rule
  per field). `source_pattern(CardClass)` routes the queries a card raises
  (`GameRef(card=frozenset({("printed", CardClass)}))`). An empty `GameRef()`
  is the **Baseline Intent** (system queries) — set it with
  `player.set_baseline(Intent(...))`.
- `preferences: tuple[PlayerDecision, ...]` — scanned in order; the first offered
  option that `satisfies` a preference wins. Build with the smart constructors:
  `Decision.obj(instance=bear.instance_id)`, `Decision.obj(printed=LlanowarElves)`,
  `Decision.ability(printed=LlanowarElvesAbility1)`, `Decision.mode(printed=…)`,
  `Decision.yes()`, `Decision.number(3)`, `Decision.mana(color="R")`, …
- `branches` — instead of `preferences`, several preference lists. The intent
  owns the retries of the choices it answers: when the engine rejects one, the
  choice is retried with the intent's next branch, and with none left the test
  fails with `PostconditionError`. With `preferences` alone there is one
  branch, so a rejection fails. Each new cast or choice starts again from the
  first branch.
- `postcondition: (game) -> bool | None` — checked at `end_intent`; raises
  `PostconditionError` if it does not hold.

Lifecycle: `player.start_intent(name, intent)` → actions → `player.end_intent(name)`.

Preference helpers:

- `prefer(player, *decisions)` — set the player's Baseline Intent to prefer
  `decisions`, in order.
- `object_preference(game, card)` — a preference for `card` in its current zone.

Every query a player answers is logged on `player.transcript`:
`transcript.priority_queries()` lists the Priority Queries, and
`transcript.queries(kind)` the other queries of a Decision kind.

## Canonical test shape

```python
from cards.fdn.fdn_215.card_impl import Bushwhack, BushwhackAbility3
from cards.fdn.fdn_227.card_impl import LlanowarElves
from engine.decisions import Decision
from test_utils import Intent
from engine.types import ManaType, Phase
from test_utils import (
    act, advance_to_phase, create_game, put_on_battlefield, resolve_stack,
    run_scripts, script, set_board_state, source_pattern,
)


def test_bushwhack_fight():
    game = create_game()
    p0, p1 = game.players
    ally = put_on_battlefield(game, p0, LlanowarElves())
    elves = put_on_battlefield(game, p1, LlanowarElves())
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    set_board_state(game, 0, hand=[Bushwhack()], mana={ManaType.GREEN: 1})

    p0.start_intent("fight", Intent(
        pattern=source_pattern(Bushwhack),
        preferences=(
            Decision.mode(printed=BushwhackAbility3),   # the fight mode
            Decision.obj(instance=ally.instance_id),
            Decision.obj(instance=elves.instance_id),
        ),
    ))
    script(game, 0, act(Bushwhack))
    run_scripts(game)        # Bushwhack is cast; the stack is left in place
    resolve_stack(game)
    p0.end_intent("fight")

    assert elves in game.get_graveyard(p1).get_all()
```

## Constraints

- **Max 30 tests per card.**
- Import helpers from `test_utils`; cards and their predefined classes from
  `cards.fdn.fdn_<N>.card_impl` (target stubs and reference cards alike).
