"""Tests for SOS 163 — Tenured Concocter.

A 4/5 Troll Druid for {4}{G} with:
- Vigilance
- Whenever this creature becomes the target of a spell or ability an
  opponent controls, you may draw a card.
- Infusion — Gets +2/+0 as long as you gained life this turn.
"""

from __future__ import annotations

from cards.sos.sos_163.card_impl import TenuredConcocter
from engine.card import Creature
from engine.types import Keyword, ManaCost
from test_utils import create_game


class TestTenuredConcoctorProperties:
    """Static card data should match the SOS 163 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(TenuredConcocter(owner=None), Creature)

    def test_name(self) -> None:
        assert TenuredConcocter(owner=None).name == "Tenured Concocter"

    def test_mana_cost(self) -> None:
        assert TenuredConcocter(owner=None).mana_cost == ManaCost.parse("{4}{G}")

    def test_power_toughness(self) -> None:
        card = TenuredConcocter(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 5

    def test_has_vigilance(self) -> None:
        card = TenuredConcocter(owner=None)
        assert Keyword.VIGILANCE in card.keywords


class TestTenuredConcoctorTargetedDraw:
    """Whenever targeted by opponent's spell or ability, may draw a card."""

    def test_draw_card_when_targeted_by_opponent(self) -> None:
        """Should draw a card when opponent targets this creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TenuredConcocter(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        hand_size_before = len(game.get_hand(p1))
        # Simulate being targeted by opponent
        card.on_targeted(game, source_controller=p2)
        assert len(game.get_hand(p1)) == hand_size_before + 1

    def test_no_draw_when_targeted_by_own_spell(self) -> None:
        """Should NOT draw when targeted by own spell."""
        game = create_game()
        p1 = game.players[0]
        card = TenuredConcocter(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        hand_size_before = len(game.get_hand(p1))
        card.on_targeted(game, source_controller=p1)
        assert len(game.get_hand(p1)) == hand_size_before


class TestTenuredConcoctorInfusion:
    """Infusion — gets +2/+0 as long as you gained life this turn."""

    def test_no_bonus_without_life_gain(self) -> None:
        """Without life gain this turn, power should be base 4."""
        game = create_game()
        p1 = game.players[0]
        card = TenuredConcocter(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        assert card.get_power(game) == 4

    def test_plus_two_power_after_life_gain(self) -> None:
        """After gaining life this turn, power should be 6 (4+2)."""
        game = create_game()
        p1 = game.players[0]
        card = TenuredConcocter(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        # Simulate life gain this turn
        p1.life_gained_this_turn = 1
        assert card.get_power(game) == 6

    def test_toughness_unaffected_by_infusion(self) -> None:
        """Infusion only gives +2/+0, toughness stays at 5."""
        game = create_game()
        p1 = game.players[0]
        card = TenuredConcocter(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        p1.life_gained_this_turn = 3
        assert card.get_toughness(game) == 5
