"""Audited tests for Swiftwater Cliffs (FDN collector number 268)."""
from __future__ import annotations
import pytest
from card_impl import SwiftwaterCliffs
from engine.card import Land
from engine.types import ManaType
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestSwiftwaterCliffsBasic:
    def test_is_land(self) -> None:
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=None)
        assert isinstance(card, Land)

    def test_enters_tapped(self) -> None:
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=None)
        assert card.enters_tapped is True

    def test_register_triggers_taps_card(self) -> None:
        game = create_game()
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=game.players[0])
        card.controller = game.players[0]
        card.register_triggers(game)
        assert card.is_tapped


@pytest.mark.ability
class TestSwiftwaterCliffsAbilities:
    def test_etb_gains_one_life(self) -> None:
        game = create_game()
        p = game.players[0]
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=p)
        card.controller = p
        life_before = p.life
        card.register_triggers(game)
        assert p.life == life_before + 1

    def test_has_two_mana_abilities(self) -> None:
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=None)
        assert len(card.get_mana_abilities()) == 2

    def test_taps_for_u(self) -> None:
        game = create_game()
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.BLUE) >= 1

    def test_taps_for_r(self) -> None:
        game = create_game()
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        card.is_tapped = False
        abilities = card.get_mana_abilities()
        abilities[1].cost(game, card)
        abilities[1].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.RED) >= 1

    def test_cannot_tap_when_tapped(self) -> None:
        game = create_game()
        card = SwiftwaterCliffs(name="Swiftwater Cliffs", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert abilities[0].cost(game, card) is False
