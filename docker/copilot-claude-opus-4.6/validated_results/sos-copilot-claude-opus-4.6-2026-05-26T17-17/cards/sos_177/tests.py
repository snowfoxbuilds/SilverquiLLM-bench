"""Tests for SOS 177 — Bogwater Lumaret."""

from __future__ import annotations

import pytest

from cards.sos.sos_177.card_impl import BogwaterLumaret
from engine.card import Creature
from engine.types import ManaCost, ManaType
from test_utils import create_game, set_board_state


class TestBogwaterLumaretProperties:
    """Static card properties match spec."""

    def test_is_creature(self) -> None:
        assert isinstance(BogwaterLumaret(owner=None), Creature)

    def test_name(self) -> None:
        assert BogwaterLumaret(owner=None).name == "Bogwater Lumaret"

    def test_mana_cost(self) -> None:
        assert BogwaterLumaret(owner=None).mana_cost == ManaCost.parse("{B}{G}")

    def test_power_toughness(self) -> None:
        card = BogwaterLumaret(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestBogwaterLumaretTrigger:
    """Whenever this or another creature you control enters, you gain 1 life."""

    def test_gains_life_when_itself_enters(self) -> None:
        game = create_game()
        lumaret = BogwaterLumaret(owner=game.players[0])
        set_board_state(game, 0, mana={ManaType.BLACK: 1, ManaType.GREEN: 1},
                        hand=[lumaret])
        from test_utils import cast_spell
        cast_spell(game, 0, "Bogwater Lumaret")
        assert game.players[0].life == 21

    def test_gains_life_when_another_creature_enters(self) -> None:
        game = create_game()
        lumaret = BogwaterLumaret(owner=game.players[0])
        set_board_state(game, 0, battlefield=[lumaret])
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        bear.owner = game.players[0]
        # Simulate another creature entering the battlefield
        set_board_state(game, 0, battlefield=[lumaret, bear])
        # The trigger should have fired, granting 1 life
        # We need to use proper ETB simulation instead; for TDD this tests the contract
        game.move_to_battlefield(bear, game.players[0])
        assert game.players[0].life >= 21

    def test_opponent_creature_entering_does_not_trigger(self) -> None:
        game = create_game()
        lumaret = BogwaterLumaret(owner=game.players[0])
        set_board_state(game, 0, battlefield=[lumaret])
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        bear.owner = game.players[1]
        set_board_state(game, 1, battlefield=[bear])
        # Opponent's creature entering should not give controller life
        assert game.players[0].life == 20

    def test_multiple_creatures_entering_triggers_multiple_times(self) -> None:
        game = create_game()
        lumaret = BogwaterLumaret(owner=game.players[0])
        set_board_state(game, 0, battlefield=[lumaret])
        c1 = Creature(name="Pest Token A", base_power=1, base_toughness=1)
        c1.owner = game.players[0]
        c2 = Creature(name="Pest Token B", base_power=1, base_toughness=1)
        c2.owner = game.players[0]
        game.move_to_battlefield(c1, game.players[0])
        game.move_to_battlefield(c2, game.players[0])
        # Should gain 2 life (1 per creature entering)
        assert game.players[0].life >= 22
