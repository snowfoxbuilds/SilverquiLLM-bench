"""Audited tests for FDN 86 — Fiery Annihilation."""

from __future__ import annotations

from card_impl import FieryAnnihilation
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestFieryAnnihilationBasics:
    """Basic card properties."""

    def test_is_instant(self) -> None:
        card = FieryAnnihilation(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = FieryAnnihilation(owner=None)
        assert card.name == "Fiery Annihilation"

    def test_mana_cost(self) -> None:
        card = FieryAnnihilation(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestFieryAnnihilationResolve:
    """Deals 5 damage to target creature; exile replacement on death."""

    def test_deals_5_damage_to_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = FieryAnnihilation(owner=p1, controller=p1)
        target = Creature(name="Target", base_power=2, base_toughness=6, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert getattr(target, "damage_marked", 0) == 5

    def test_sets_exile_on_death_flag(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = FieryAnnihilation(owner=p1, controller=p1)
        target = Creature(name="Target", base_power=2, base_toughness=8, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        assert getattr(target, "_exile_on_death", False) is True

    def test_fizzles_when_target_is_none(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = FieryAnnihilation(owner=p1, controller=p1)
        card.chosen_targets = [None]
        # Should not crash
        card.on_resolve(game)

    def test_kills_small_creature(self) -> None:
        """5 damage kills a 2-toughness creature."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = FieryAnnihilation(owner=p1, controller=p1)
        target = Creature(name="Small", base_power=1, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        card.chosen_targets = [target]
        card.on_resolve(game)
        # Creature took lethal damage
        assert getattr(target, "damage_marked", 0) >= target.base_toughness
