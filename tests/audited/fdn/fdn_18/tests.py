"""Audited tests for FDN 18 — Inspiring Paladin."""

from __future__ import annotations

from card_impl import InspiringPaladin
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game


class TestInspiringPaladinBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = InspiringPaladin(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = InspiringPaladin(owner=None)
        assert card.name == "Inspiring Paladin"

    def test_mana_cost(self) -> None:
        card = InspiringPaladin(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}")

    def test_power_toughness(self) -> None:
        card = InspiringPaladin(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = InspiringPaladin(owner=None)
        assert "Human" in card.subtypes
        assert "Knight" in card.subtypes


class TestInspiringPaladinFirstStrike:
    """During your turn, has first strike + grants it to creatures with counters."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        paladin = InspiringPaladin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(paladin)
        paladin.register_triggers(game)
        return game, p1, paladin

    def test_has_first_strike_on_own_turn(self) -> None:
        game, p1, paladin = self._setup()
        game.active_player_index = 0
        game.effect_manager.apply_all(game)
        assert Keyword.FIRST_STRIKE in paladin.keywords

    def test_no_first_strike_on_opponent_turn(self) -> None:
        game, p1, paladin = self._setup()
        game.active_player_index = 1
        game.effect_manager.apply_all(game)
        assert Keyword.FIRST_STRIKE not in paladin.keywords

    def test_creature_with_counter_gets_first_strike_on_own_turn(self) -> None:
        game, p1, paladin = self._setup()
        from engine.game import add_counter
        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        add_counter(game, other, "+1/+1", 1)
        other._original_plus_one_counters = other.plus_one_counters
        game.active_player_index = 0
        game.effect_manager.apply_all(game)
        assert Keyword.FIRST_STRIKE in other.keywords

    def test_creature_without_counter_no_first_strike(self) -> None:
        game, p1, paladin = self._setup()
        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        game.active_player_index = 0
        game.effect_manager.apply_all(game)
        assert Keyword.FIRST_STRIKE not in other.keywords
