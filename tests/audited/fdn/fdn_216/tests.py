"""Audited tests for FDN 216 — Doubling Season."""

from __future__ import annotations

from card_impl import DoublingSeason
from engine.card import Creature, Enchantment
from engine.replacement_effects import ReplacementEffect
from engine.types import ManaCost
from tests.test_utils import create_game


class TestDoublingSeasonBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = DoublingSeason(owner=None)
        assert card.name == "Doubling Season"

    def test_mana_cost(self) -> None:
        card = DoublingSeason(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{G}")

    def test_is_enchantment(self) -> None:
        card = DoublingSeason(owner=None)
        assert isinstance(card, Enchantment)


class TestDoublingSeasonTokenDoubling:
    """Token doubling replacement effect."""

    def test_doubles_token_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ds = DoublingSeason(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ds)
        ds.register_replacement_effects(game)
        event_data = {"player": p1, "count": 3}
        event_data = game.replacement_manager.apply(game, "create_token", event_data)
        assert event_data["count"] == 6

    def test_does_not_double_opponent_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ds = DoublingSeason(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ds)
        ds.register_replacement_effects(game)
        event_data = {"player": p2, "count": 3}
        event_data = game.replacement_manager.apply(game, "create_token", event_data)
        assert event_data["count"] == 3


class TestDoublingSeasonCounterDoubling:
    """Counter doubling replacement effect."""

    def test_doubles_counters_on_own_permanent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ds = DoublingSeason(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ds)
        ds.register_replacement_effects(game)
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        event_data = {"permanent": creature, "amount": 2}
        event_data = game.replacement_manager.apply(game, "add_counter", event_data)
        assert event_data["amount"] == 4

    def test_does_not_double_opponent_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        ds = DoublingSeason(owner=p1, controller=p1)
        game.get_battlefield(p1).add(ds)
        ds.register_replacement_effects(game)
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(creature)
        event_data = {"permanent": creature, "amount": 2}
        event_data = game.replacement_manager.apply(game, "add_counter", event_data)
        assert event_data["amount"] == 2

