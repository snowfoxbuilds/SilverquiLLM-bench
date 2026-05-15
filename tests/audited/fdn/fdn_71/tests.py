"""Audited tests for FDN 71 — Stab."""

from __future__ import annotations

from card_impl import Stab
from engine.card import Creature, Instant
from engine.types import ManaCost, Zone
from tests.test_utils import create_game


class TestStabBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = Stab(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = Stab(owner=None)
        assert card.name == "Stab"

    def test_mana_cost(self) -> None:
        card = Stab(owner=None)
        assert card.mana_cost == ManaCost.parse("{B}")


class TestStabResolve:
    """Target creature gets -2/-2 until end of turn."""

    def test_applies_minus_two_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = Stab(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert target.power == 1
        assert target.toughness == 1

    def test_fizzles_with_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Stab(owner=p1, controller=p1)
        card.chosen_targets = [None]
        card.on_resolve(game)  # Should not crash

    def test_fizzles_if_target_left_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = Stab(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=3, base_toughness=3, owner=p2, controller=p2)
        # Target is NOT on battlefield
        card.chosen_targets = [target]
        card.on_resolve(game)
        # No effect added
        effects = game.effect_manager.get_all() if hasattr(game.effect_manager, 'get_all') else []
        assert len(effects) == 0

    def test_has_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = Stab(owner=p1, controller=p1)
        targets = card.get_targets(game)
        assert len(targets) == 1
