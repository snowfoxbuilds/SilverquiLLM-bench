"""Tests for SOS 159 — Shopkeeper's Bane."""

from __future__ import annotations

from cards.sos.sos_159.card_impl import ShopkeepersBane
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestShopkeepersBaneProperties:
    """Static card data should match the SOS 159 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ShopkeepersBane(owner=None), Creature)

    def test_name(self) -> None:
        assert ShopkeepersBane(owner=None).name == "Shopkeeper's Bane"

    def test_mana_cost(self) -> None:
        assert ShopkeepersBane(owner=None).mana_cost == ManaCost.parse("{2}{G}")

    def test_power_toughness(self) -> None:
        bane = ShopkeepersBane(owner=None)
        assert bane.power == 4
        assert bane.toughness == 2

    def test_has_trample(self) -> None:
        bane = ShopkeepersBane(owner=None)
        assert Keyword.TRAMPLE in bane.keywords


class TestShopkeepersBaneAttackTrigger:
    """Whenever this creature attacks, you gain 2 life."""

    def test_gains_two_life_on_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bane = ShopkeepersBane(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bane], life=20)

        bane.declare_attack(game)
        game.process_triggers()

        assert p1.life == 22

    def test_no_life_gain_without_attack(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bane = ShopkeepersBane(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bane], life=20)

        # No attack declared — life should remain unchanged
        assert p1.life == 20
