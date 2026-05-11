"""Audited tests for Wind-Scarred Crag (FDN collector number 271)."""
from __future__ import annotations
import pytest
from card_impl import WindScarredCrag
from engine.card import Land
from engine.types import ManaType
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestWindScarredCragBasic:
    def test_is_land(self) -> None:
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=None)
        assert isinstance(card, Land)

    def test_enters_tapped(self) -> None:
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=None)
        assert card.enters_tapped is True

    def test_register_triggers_taps_card(self) -> None:
        game = create_game()
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=game.players[0])
        card.controller = game.players[0]
        card.register_triggers(game)
        assert card.is_tapped


@pytest.mark.ability
class TestWindScarredCragAbilities:
    def test_etb_gains_one_life(self) -> None:
        game = create_game()
        p = game.players[0]
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=p)
        card.controller = p
        life_before = p.life
        card.register_triggers(game)
        assert p.life == life_before + 1

    def test_has_two_mana_abilities(self) -> None:
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=None)
        assert len(card.get_mana_abilities()) == 2

    def test_taps_for_r(self) -> None:
        game = create_game()
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.RED) >= 1

    def test_taps_for_w(self) -> None:
        game = create_game()
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        card.is_tapped = False
        abilities = card.get_mana_abilities()
        abilities[1].cost(game, card)
        abilities[1].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.WHITE) >= 1

    def test_cannot_tap_when_tapped(self) -> None:
        game = create_game()
        card = WindScarredCrag(name="Wind-Scarred Crag", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert abilities[0].cost(game, card) is False
