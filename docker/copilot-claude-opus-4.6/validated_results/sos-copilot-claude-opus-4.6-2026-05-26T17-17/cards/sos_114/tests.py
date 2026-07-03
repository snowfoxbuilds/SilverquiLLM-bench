"""Tests for SOS 114 — Expressive Firedancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_114.card_impl import ExpressiveFiredancer
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestExpressiveFiredancerProperties:
    """Static card data should match spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ExpressiveFiredancer(owner=None), Creature)

    def test_name(self) -> None:
        assert ExpressiveFiredancer(owner=None).name == "Expressive Firedancer"

    def test_mana_cost(self) -> None:
        assert ExpressiveFiredancer(owner=None).mana_cost == ManaCost.parse("{1}{R}")

    def test_power_toughness(self) -> None:
        card = ExpressiveFiredancer(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestExpressiveFiredancerOpusTrigger:
    """Opus — gets +1/+1 on instant/sorcery cast."""

    def test_gets_plus_one_on_instant_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Simulate casting an instant
        spell = Instant(name="Shock", owner=p1, controller=p1)
        spell.mana_spent = 1
        card.on_instant_or_sorcery_cast(game, spell)

        assert card.get_power(game) == 3
        assert card.get_toughness(game) == 3

    def test_gets_plus_one_on_sorcery_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        spell = Sorcery(name="Lava Axe", owner=p1, controller=p1)
        spell.mana_spent = 3
        card.on_instant_or_sorcery_cast(game, spell)

        assert card.get_power(game) == 3
        assert card.get_toughness(game) == 3

    def test_bonus_is_until_end_of_turn(self) -> None:
        """The +1/+1 bonus is temporary (until end of turn)."""
        game = create_game()
        p1 = game.players[0]
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        spell = Instant(name="Shock", owner=p1, controller=p1)
        spell.mana_spent = 1
        card.on_instant_or_sorcery_cast(game, spell)

        # After end of turn cleanup
        card.end_of_turn_cleanup(game)

        assert card.get_power(game) == 2
        assert card.get_toughness(game) == 2


class TestExpressiveFiredancerDoubleStrike:
    """Gains double strike when 5+ mana spent on the spell."""

    def test_gains_double_strike_with_five_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        spell = Instant(name="Big Spell", owner=p1, controller=p1)
        spell.mana_spent = 5
        card.on_instant_or_sorcery_cast(game, spell)

        assert Keyword.DOUBLE_STRIKE in card.keywords
        assert card.get_power(game) == 3
        assert card.get_toughness(game) == 3

    def test_no_double_strike_with_four_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        spell = Instant(name="Medium Spell", owner=p1, controller=p1)
        spell.mana_spent = 4
        card.on_instant_or_sorcery_cast(game, spell)

        assert Keyword.DOUBLE_STRIKE not in card.keywords
        # Still gets +1/+1 though
        assert card.get_power(game) == 3

    def test_double_strike_until_end_of_turn(self) -> None:
        """Double strike is also temporary."""
        game = create_game()
        p1 = game.players[0]
        card = ExpressiveFiredancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        spell = Instant(name="Big Spell", owner=p1, controller=p1)
        spell.mana_spent = 6
        card.on_instant_or_sorcery_cast(game, spell)

        assert Keyword.DOUBLE_STRIKE in card.keywords

        card.end_of_turn_cleanup(game)

        assert Keyword.DOUBLE_STRIKE not in card.keywords
