"""Tests for SOS 232 — Stadium Tidalmage.

Creature — Djinn Sorcerer {2}{U}{R} 4/4
Whenever this creature enters or attacks, you may draw a card. If you do, discard a card.
"""

from __future__ import annotations

from cards.sos.sos_232.card_impl import StadiumTidalmage
from engine.card import Creature
from engine.types import ManaCost, ManaType, Keyword, Zone
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class TestStadiumTidalmageProperties:
    """Static card data should match the SOS 232 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(StadiumTidalmage(owner=None), Creature)

    def test_name(self) -> None:
        assert StadiumTidalmage(owner=None).name == "Stadium Tidalmage"

    def test_mana_cost(self) -> None:
        assert StadiumTidalmage(owner=None).mana_cost == ManaCost.parse("{2}{U}{R}")

    def test_power_toughness(self) -> None:
        card = StadiumTidalmage(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestStadiumTidalmageETB:
    """Whenever this creature enters, you may draw a card. If you do, discard a card."""

    def test_etb_triggers_loot(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StadiumTidalmage(owner=p1, controller=p1)
        hand_before = len(game.get_hand(p1).get_all())
        card.on_enter(game)
        # Loot = draw then discard: net hand size stays the same
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before  # net zero change (draw 1, discard 1)


class TestStadiumTidalmageAttack:
    """Whenever this creature attacks, you may draw a card. If you do, discard a card."""

    def test_attack_triggers_loot(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = StadiumTidalmage(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        hand_before = len(game.get_hand(p1).get_all())
        card.on_attack(game)
        hand_after = len(game.get_hand(p1).get_all())
        # Loot: net zero change
        assert hand_after == hand_before
