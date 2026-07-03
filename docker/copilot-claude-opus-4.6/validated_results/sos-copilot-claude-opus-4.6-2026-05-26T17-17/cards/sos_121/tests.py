"""Tests for SOS 121 — Living History."""

from __future__ import annotations

import pytest

from cards.sos.sos_121.card_impl import LivingHistory
from engine.card import Creature, Enchantment
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell, declare_attackers


class TestLivingHistoryProperties:
    """Static card data should match the SOS 121 spec."""

    def test_is_enchantment(self) -> None:
        card = LivingHistory(owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        assert LivingHistory(owner=None).name == "Living History"

    def test_mana_cost(self) -> None:
        assert LivingHistory(owner=None).mana_cost == ManaCost.parse("{1}{R}")


class TestLivingHistoryETB:
    """When Living History enters, create a 2/2 red and white Spirit creature token."""

    def test_creates_spirit_token_on_etb(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[LivingHistory(owner=None)],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Living History")
        battlefield = game.get_battlefield(game.players[0])
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        assert len(tokens) >= 1
        spirit = tokens[0]
        assert spirit.base_power == 2
        assert spirit.base_toughness == 2
        assert "Spirit" in spirit.name or "Spirit" in getattr(spirit, 'subtypes', set())

    def test_spirit_token_is_red_and_white(self) -> None:
        game = create_game()
        set_board_state(game, 0, hand=[LivingHistory(owner=None)],
                        mana={ManaType.RED: 1, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Living History")
        battlefield = game.get_battlefield(game.players[0])
        tokens = [c for c in battlefield if getattr(c, 'is_token', False)]
        assert len(tokens) >= 1
        spirit = tokens[0]
        colors = getattr(spirit, 'colors', set())
        assert "R" in colors and "W" in colors


class TestLivingHistoryAttackTrigger:
    """Whenever you attack, if a card left your graveyard this turn, target attacking creature gets +2/+0."""

    def test_attack_trigger_with_graveyard_departure(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LivingHistory(owner=p1, controller=p1)
        attacker = Creature(name="Test Warrior", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        attacker.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[card, attacker])
        # Simulate a card leaving graveyard this turn
        game.mark_graveyard_departure(p1)
        declare_attackers(game, ["Test Warrior"])
        # Attacker should get +2/+0
        assert attacker.get_power() >= 4

    def test_attack_trigger_without_graveyard_departure_no_bonus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LivingHistory(owner=p1, controller=p1)
        attacker = Creature(name="Test Warrior", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        attacker.card_types = {CardType.CREATURE}
        set_board_state(game, 0, battlefield=[card, attacker])
        declare_attackers(game, ["Test Warrior"])
        # No graveyard departure, so no bonus
        assert attacker.get_power() == 2
