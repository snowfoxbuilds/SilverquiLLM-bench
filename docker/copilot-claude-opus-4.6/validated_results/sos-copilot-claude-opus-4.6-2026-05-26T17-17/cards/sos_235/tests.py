"""Tests for SOS 235 — Stress Dream.

Instant {3}{U}{R}
Stress Dream deals 5 damage to up to one target creature. Look at the top
two cards of your library. Put one of those cards into your hand and the
other on the bottom of your library.
"""

from __future__ import annotations

from cards.sos.sos_235.card_impl import StressDream
from engine.card import Creature, Instant
from engine.types import ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestStressDreamProperties:
    """Static card data should match the SOS 235 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(StressDream(owner=None), Instant)

    def test_name(self) -> None:
        assert StressDream(owner=None).name == "Stress Dream"

    def test_mana_cost(self) -> None:
        assert StressDream(owner=None).mana_cost == ManaCost.parse("{3}{U}{R}")


class TestStressDreamDamage:
    """Deals 5 damage to up to one target creature."""

    def test_deals_5_damage_to_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Hill Giant", base_power=3, base_toughness=5)
        set_board_state(game, 1, battlefield=[target])
        card = StressDream(owner=p1, controller=p1)
        card.on_resolve(game, target=target)
        assert target.damage_taken >= 5

    def test_kills_creature_with_5_or_less_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = StressDream(owner=p1, controller=p1)
        card.on_resolve(game, target=target)
        bf = game.get_battlefield(game.players[1]).get_all()
        assert target not in bf

    def test_up_to_one_can_choose_no_target(self) -> None:
        """'Up to one' allows casting with no target creature."""
        game = create_game()
        p1 = game.players[0]
        card = StressDream(owner=p1, controller=p1)
        # Should not error with no target
        card.on_resolve(game, target=None)


class TestStressDreamLook:
    """Look at top 2 cards, put one in hand and other on bottom."""

    def test_puts_one_card_into_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StressDream(owner=p1, controller=p1)
        hand_before = len(game.get_hand(p1).get_all())
        card.on_resolve(game, target=None)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after - hand_before == 1

    def test_library_decreases_by_one_net(self) -> None:
        """Two cards looked at, one to hand, one to bottom = net -1 from top."""
        game = create_game()
        p1 = game.players[0]
        card = StressDream(owner=p1, controller=p1)
        lib_before = len(game.get_library(p1).get_all())
        card.on_resolve(game, target=None)
        lib_after = len(game.get_library(p1).get_all())
        # One card moved from library to hand; the other stays in library (bottom)
        assert lib_after == lib_before - 1
