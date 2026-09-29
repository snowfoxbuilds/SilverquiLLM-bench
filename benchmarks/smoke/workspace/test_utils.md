# Test Utilities API Reference

Helper functions for writing card tests. Import from `test_utils`.

Choices are answered through the **Player Query / Player Decision** protocol: the
engine raises a Player Query; the intent-based `DeterministicPlayer` answers it
by routing to an active **Intent** and selecting the first offered option that
satisfies one of the intent's **preferences**. There is no positional choice
script — `set_board_state` and the action directives below survive, but the
choice channel is Intents.

## Two channels

- **Action channel (directives)** — what a player *does*: `cast_spell`,
  `declare_attackers`, `declare_blockers`, `advance_to_phase`. Imperative.
- **Choice channel (Intents)** — how a player *answers a forced choice* raised
  while an action resolves: targets, modes, ordering, sacrifices, discards.
  Declared up front via `player.start_intent(name, Intent(...))`.

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
it is placed in) that a test can reference in an Intent preference.

### `put_on_battlefield`

`put_on_battlefield(game, player, card) -> card`

Place one card on `player`'s battlefield and return it with `card.instance_id`
set — the idiomatic way to obtain an object to target.

```python
from test_utils import create_game, put_on_battlefield
from engine.card import Creature
from engine.types import ManaCost

game = create_game()
bear = put_on_battlefield(game, game.players[1],
                          Creature(name="Bear", mana_cost=ManaCost(generic=1),
                                   base_power=2, base_toughness=2))
```

## Actions

### `cast_spell`

`cast_spell(game, player_index, card_name, targets=None) -> None`

Find a card in hand by name, cast it, and resolve. Sets sorcery-speed timing
automatically. If `targets` is given, a transient Intent is started that prefers
those objects (by `instance_id`) / players (by seat) for the target query the
engine raises during casting — a convenience over writing the Intent yourself.

### `declare_attackers` / `declare_blockers`

`declare_attackers(game, attacker_names) -> None`
`declare_blockers(game, assignments) -> None`  (`{"attacker": ["blocker", ...]}`)

Action-layer directives — the chosen creatures are passed straight to the
engine's combat steps (no query). When an attacker is multi-blocked the engine
raises a damage-order Player Query to the attacker's controller; give that
player a Baseline Intent if your test reaches that case.

### `advance_to_phase`

`advance_to_phase(game, phase, step=None) -> None` — fast-forward without granting priority.
It only sets the phase: no untap, draw, upkeep or end-step events fire.

### `advance_game_to_phase`

`advance_game_to_phase(game, phase, step=None) -> None` — drive real phase
transitions to `phase`/`step`: untap, draw, the upkeep, beginning-of-combat and
end-step events, combat damage and cleanup all happen, resolving the stack on
the way. Use it when a test depends on delayed or "at the beginning of" triggers.

### `resolve_stack`

`resolve_stack(game) -> None` — resolve the entire stack.

### `activate_card_ability`

`activate_card_ability(game, player, source_card, index=0) -> None`

Activate ability `index` of `card_abilities(source_card)` through the engine's
real activation path (targets chosen before costs are paid). Raises
`AbilityError` when the ability cannot be activated. Resolve the stack
afterwards to run a non-mana ability's effect.

`card_abilities(card)` is the card's `get_activated_abilities()`, followed by
any `get_mana_abilities()` entries not already listed, so a mana ability can be
activated wherever the card exposes it.

`activate_loyalty_ability(game, player, source_card, index=0)` does the same for
a planeswalker's loyalty abilities.

### More setup and action helpers

- `enter_permanent(game, player, card) -> card` — put `card` into `player`'s hand
  and move it onto the battlefield through the real zone transition, so its
  enters-the-battlefield events and triggers fire.
- `cast_card(game, player, card, resolve=True)` — cast a card that is unzoned or
  in the caster's hand; the test supplies mana and Intents.
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

## Intents (the choice channel)

```python
from engine.intent_player import Intent
from engine.decisions import Decision, GameRef
```

`Intent(pattern, preferences=(), postcondition=None)`:

- `pattern: GameRef` — routes a query by matching its source refs (subset rule
  per field). Route a card's queries with `GameRef(card=frozenset({("name", "<Card Name>")}))`.
  An empty `GameRef()` is the **Baseline Intent** (system queries) — set it with
  `player.set_baseline(Intent(...))`.
- `preferences: tuple[PlayerDecision, ...]` — scanned in order; the first offered
  option that `satisfies` a preference wins. Build with the smart constructors:
  `Decision.obj(instance=bear.instance_id)`, `Decision.obj(color="R")`,
  `Decision.yes()`, `Decision.number(3)`, `Decision.mana(color="R")`, …
- `postcondition: (game) -> bool | None` — checked at `end_intent`; raises
  `PostconditionError` if it does not hold.

Lifecycle: `player.start_intent(name, intent)` → actions → `player.end_intent(name)`.

Preference helpers:

- `prefer(player, *decisions)` — set the player's Baseline Intent to prefer
  `decisions`, in order.
- `object_preference(game, card)` — a preference for `card` in its current zone.
- `payment_preference(game, source)` — preferences that activate `source`'s mana
  ability while paying a cost, whether the engine asks for the permanent or for
  one of its abilities. Use it as `prefer(player, *payment_preference(game, source))`.

## Canonical test shape

```python
from test_utils import create_game, put_on_battlefield, set_board_state, cast_spell, resolve_stack
from engine.intent_player import Intent
from engine.decisions import Decision, GameRef, DecisionKind
from cards.fdn.fdn_215.card_impl import Bushwhack

def test_bushwhack_fight(game=None):
    game = create_game()
    p0 = game.players[0]
    bear = put_on_battlefield(game, game.players[1], some_creature())
    set_board_state(game, 0, hand=[Bushwhack(owner=None)])

    p0.start_intent("fight", Intent(
        pattern=GameRef(card=frozenset({("name", "Bushwhack")})),
        preferences=(Decision.obj(instance=bear.instance_id),),
        postcondition=lambda g: bear in g.get_graveyard(game.players[1]).get_all(),
    ))
    cast_spell(game, 0, "Bushwhack")
    p0.end_intent("fight")  # postcondition checked here

    # Option-set invariant over the transcript: the engine never offered an
    # illegal target (e.g. a hexproof creature).
    offered = p0.transcript.queries(kind=DecisionKind.OBJECT)[-1].options
    assert not any(("keyword", "hexproof") in opt.attrs for opt in offered)
```

## Constraints

- **Max 30 tests per card.**
- Import helpers from `test_utils`; cards from `cards.fdn.fdn_<N>.card_impl`
  (target stubs and reference cards alike).
