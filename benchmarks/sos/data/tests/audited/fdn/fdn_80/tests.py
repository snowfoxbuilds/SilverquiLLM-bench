"""Audited tests for FDN 80 — Bulk Up."""

from __future__ import annotations

from card_impl import BulkUp
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


class TestBulkUpBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = BulkUp(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = BulkUp(owner=None)
        assert card.name == "Bulk Up"

    def test_mana_cost(self) -> None:
        card = BulkUp(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_has_flashback_cost(self) -> None:
        card = BulkUp(owner=None)
        assert card.flashback_cost == ManaCost.parse("{4}{R}{R}")


class TestBulkUpResolve:
    """Double target creature's power until end of turn."""

    def test_doubles_target_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BulkUp(owner=p1, controller=p1)
        target = Creature(name="Target", base_power=3, base_toughness=3, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert target.modified_power == 6

    def test_doubles_power_of_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BulkUp(owner=p1, controller=p1)
        target = Creature(name="Small", base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert target.modified_power == 2

    def test_fizzles_when_target_is_none(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BulkUp(owner=p1, controller=p1)
        card.chosen_targets = [None]
        # Should not crash
        card.on_resolve(game)

    def test_does_not_change_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BulkUp(owner=p1, controller=p1)
        target = Creature(name="Target", base_power=4, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target.base_toughness == 5

    def test_doubles_zero_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BulkUp(owner=p1, controller=p1)
        target = Creature(name="Wall", base_power=0, base_toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert target.base_power == 0
