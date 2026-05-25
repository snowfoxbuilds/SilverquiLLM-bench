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
from cards.card_impl import Bear, BoltCard

game = create_game()
set_board_state(game, 0, hand=[BoltCard()], mana={ManaType.RED: 2})
set_board_state(game, 1, battlefield=[Bear()], life=15)
```

### `cast_spell`

`cast_spell(game, player_index, card_name, targets=None) -> None`

Find a card in hand by name, cast it, and resolve. Sets sorcery-speed timing automatically.

```python
from test_utils import create_game, set_board_state, cast_spell
from engine.types import ManaType
from cards.card_impl import HealingCard

game = create_game()
set_board_state(game, 0, hand=[HealingCard()], mana={ManaType.WHITE: 2})
cast_spell(game, 0, "HealingCard")
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
from cards.card_impl import Bear

game = create_game()
set_board_state(game, 0, battlefield=[Bear()])
declare_attackers(game, ["Bear"])
```

### `declare_blockers`

`declare_blockers(game, assignments) -> None`

Assign blockers by name mapping: `{"attacker_name": ["blocker_name", ...]}`.

```python
from test_utils import create_game, set_board_state, declare_attackers, declare_blockers
from cards.card_impl import Bear, Wall

game = create_game()
set_board_state(game, 0, battlefield=[Bear()])
set_board_state(game, 1, battlefield=[Wall()])
declare_attackers(game, ["Bear"])
declare_blockers(game, {"Bear": ["Wall"]})
```

## Test Structure

```python
import pytest
from test_utils import create_game, set_board_state, cast_spell
from cards.card_impl import MyCard
from engine.types import ManaType

class TestMyCard:
    def test_basic_cast(self):
        game = create_game()
        set_board_state(game, 0, hand=[MyCard()], mana={ManaType.WHITE: 3})
        cast_spell(game, 0, "MyCard")
        assert game.players[0].life == 20
```

## Constraints

- **Max 30 tests per card.**
- Import helpers from `test_utils`.
- Import card implementations from `cards.card_impl`.
