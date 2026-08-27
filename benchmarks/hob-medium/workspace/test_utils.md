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

### `resolve_stack`

`resolve_stack(game) -> None` — resolve the entire stack.

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
- Import helpers from `test_utils`; cards from `cards.hob.hob_<N>.card_impl`
  (HOB cards) or `cards.fdn.fdn_<N>.card_impl` (FDN reference cards).
