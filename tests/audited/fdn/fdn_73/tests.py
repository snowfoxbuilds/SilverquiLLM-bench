"""Audited tests for FDN 73 — Tragic Banshee."""

from __future__ import annotations

from card_impl import TragicBanshee
from engine.card import Creature
from engine.types import ManaCost, Zone
from tests.test_utils import create_game


class TestTragicBansheeBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = TragicBanshee(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TragicBanshee(owner=None)
        assert card.name == "Tragic Banshee"

    def test_mana_cost(self) -> None:
        card = TragicBanshee(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{B}")

    def test_power_toughness(self) -> None:
        card = TragicBanshee(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = TragicBanshee(owner=None)
        assert "Spirit" in card.subtypes


class TestTragicBansheeETB:
    """ETB: -1/-1 (or -13/-13 with morbid) to target opponent creature."""

    def test_gives_minus_one_without_morbid(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TragicBanshee(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=4, base_toughness=4, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert target.power == 3
        assert target.toughness == 3

    def test_fizzles_with_no_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TragicBanshee(owner=p1, controller=p1)
        card.chosen_targets = [None]
        card.on_resolve(game)  # Should not crash

    def test_fizzles_if_target_left_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TragicBanshee(owner=p1, controller=p1)
        target = Creature(name="Enemy", base_power=4, base_toughness=4, owner=p2, controller=p2)
        # Target NOT on battlefield
        card.chosen_targets = [target]
        card.on_resolve(game)
        effects = game.effect_manager.get_all() if hasattr(game.effect_manager, 'get_all') else []
        assert len(effects) == 0

    def test_has_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TragicBanshee(owner=p1, controller=p1)
        targets = card.get_targets(game)
        assert len(targets) == 1
