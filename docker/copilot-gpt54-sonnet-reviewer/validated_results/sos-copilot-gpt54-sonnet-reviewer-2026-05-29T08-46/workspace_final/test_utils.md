# Test Utilities API Reference

Helper functions for writing card tests. Import from `test_utils`.

## Functions

### `create_game`

`create_game(deck1=None, deck2=None, *, player1_life=20, player2_life=20, scripts=None) -> GameState`

Create a two-player game with `DeterministicPlayer` instances. Decks default to empty lists.

```python
from test_utils import create_game
game = create_game(player1_life=25)
```

### `set_board_state`

`set_board_state(game, player_index, *, battlefield=None, hand=None, graveyard=None, life=None, mana=None) -> None`

Set zone contents and player state. Only zones explicitly provided are modified.

- **hand / battlefield / graveyard** — `list` of card objects.
- **mana** — `dict[ManaType, int]`.

```python
from test_utils import create_game, set_board_state
from engine.types import ManaType
from cards.fdn.fdn_13.card_impl import FleetingFlight
from engine.card import Creature

game = create_game()
set_board_state(game, 0, hand=[FleetingFlight(owner=None)], mana={ManaType.WHITE: 2})
bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
set_board_state(game, 1, battlefield=[bear], life=15)
```

### `cast_spell`

`cast_spell(game, player_index, card_name, targets=None) -> None`

Find a card in hand by name, cast it, and resolve. Sets sorcery-speed timing automatically.

```python
from test_utils import create_game, set_board_state, cast_spell
from engine.types import ManaType
from cards.fdn.fdn_13.card_impl import FleetingFlight

game = create_game()
set_board_state(game, 0, hand=[FleetingFlight(owner=None)], mana={ManaType.WHITE: 2})
cast_spell(game, 0, "Fleeting Flight")
```

### `advance_to_phase`

`advance_to_phase(game, phase, step=None) -> None`

Fast-forward to the specified phase/step without granting priority.

```python
from test_utils import create_game, advance_to_phase
from engine.types import Phase, Step

game = create_game()
advance_to_phase(game, Phase.COMBAT, Step.DECLARE_ATTACKERS)
```

### `declare_attackers`

`declare_attackers(game, attacker_names) -> None`

Advance to combat and declare creatures as attackers by name from the active player's battlefield.

```python
from test_utils import create_game, set_board_state, declare_attackers
from engine.card import Creature

game = create_game()
bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
set_board_state(game, 0, battlefield=[bear])
declare_attackers(game, ["Grizzly Bears"])
```

### `declare_blockers`

`declare_blockers(game, assignments) -> None`

Assign blockers by name mapping: `{"attacker_name": ["blocker_name", ...]}`.

```python
from test_utils import create_game, set_board_state, declare_attackers, declare_blockers
from engine.card import Creature

game = create_game()
bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
wall = Creature(name="Wall of Wood", base_power=0, base_toughness=3)
set_board_state(game, 0, battlefield=[bear])
set_board_state(game, 1, battlefield=[wall])
declare_attackers(game, ["Grizzly Bears"])
declare_blockers(game, {"Grizzly Bears": ["Wall of Wood"]})
```

## Test Structure

```python
import pytest
from test_utils import create_game, set_board_state, cast_spell
from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.types import ManaType

class TestTheDawningArchaic:
    def test_basic_cast(self):
        game = create_game()
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        mana={ManaType.COLORLESS: 10})
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].life == 20
```

## Constraints

- **Max 30 tests per card.**
- Import helpers from `test_utils`.
- Import card implementations from `cards.sos.sos_<N>.card_impl` (SOS cards you
  are building) or `cards.fdn.fdn_<N>.card_impl` (FDN reference cards).
