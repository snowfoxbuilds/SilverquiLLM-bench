"""Tests for SOS 103 — Ulna Alley Shopkeep.

A 2/3 Goblin Warlock for {2}{B} with Menace and
Infusion — gets +2/+0 as long as you gained life this turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_103.card_impl import UlnaAlleyShopkeep
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestUlnaAlleyShopkeepProperties:
    """Static card data should match the SOS 103 spec."""

    def test_is_creature(self) -> None:
        card = UlnaAlleyShopkeep(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert UlnaAlleyShopkeep(owner=None).name == "Ulna Alley Shopkeep"

    def test_mana_cost(self) -> None:
        assert UlnaAlleyShopkeep(owner=None).mana_cost == ManaCost.parse("{2}{B}")

    def test_power_and_toughness(self) -> None:
        card = UlnaAlleyShopkeep(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_menace(self) -> None:
        card = UlnaAlleyShopkeep(owner=None)
        assert Keyword.MENACE in card.keywords


class TestUlnaAlleyShopkeepInfusion:
    """Infusion: gets +2/+0 as long as you gained life this turn."""

    def test_no_life_gain_base_power(self) -> None:
        """Without life gain, power should be base 2."""
        game = create_game()
        p1 = game.players[0]
        card = UlnaAlleyShopkeep(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        assert card.get_power(game) == 2

    def test_life_gained_gets_plus_two(self) -> None:
        """With life gain this turn, power should be 4 (2+2)."""
        game = create_game()
        p1 = game.players[0]
        card = UlnaAlleyShopkeep(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        p1.life_gained_this_turn = 3

        assert card.get_power(game) == 4

    def test_toughness_unaffected_by_infusion(self) -> None:
        """Toughness stays at 3 regardless of life gain."""
        game = create_game()
        p1 = game.players[0]
        card = UlnaAlleyShopkeep(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        p1.life_gained_this_turn = 5

        assert card.get_toughness(game) == 3
