"""Audited tests for FDN 57 — Blasphemous Edict."""

from __future__ import annotations

from card_impl import BlasphemousEdict
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestBlasphemousEdictBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = BlasphemousEdict(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = BlasphemousEdict(owner=None)
        assert card.name == "Blasphemous Edict"

    def test_mana_cost(self) -> None:
        card = BlasphemousEdict(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}{B}")


class TestBlasphemousEdictCostReduction:
    """Alternative cost of {B} if 13+ creatures on the battlefield."""

    def test_no_reduction_below_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BlasphemousEdict(owner=p1, controller=p1)
        for i in range(12):
            c = Creature(name=f"C{i}", base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)
        assert card.cost_reduction(game) == 0

    def test_reduction_at_13_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = BlasphemousEdict(owner=p1, controller=p1)
        for i in range(7):
            c = Creature(name=f"C{i}", base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)
        for i in range(6):
            c = Creature(name=f"D{i}", base_power=1, base_toughness=1, owner=p2, controller=p2)
            game.get_battlefield(p2).add(c)
        assert card.cost_reduction(game) == 4


class TestBlasphemousEdictResolve:
    """Each player sacrifices thirteen creatures."""

    def test_sacrifices_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = BlasphemousEdict(owner=p1, controller=p1)
        for i in range(3):
            c = Creature(name=f"P1_{i}", base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)
        for i in range(2):
            c = Creature(name=f"P2_{i}", base_power=1, base_toughness=1, owner=p2, controller=p2)
            game.get_battlefield(p2).add(c)
        card.on_resolve(game)
        # All creatures sacrificed (fewer than 13 each)
        bf_p1 = [c for c in game.get_battlefield(p1).get_all() if CardType.CREATURE in getattr(c, "card_types", set())]
        bf_p2 = [c for c in game.get_battlefield(p2).get_all() if CardType.CREATURE in getattr(c, "card_types", set())]
        assert len(bf_p1) == 0
        assert len(bf_p2) == 0

    def test_no_crash_with_no_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BlasphemousEdict(owner=p1, controller=p1)
        card.on_resolve(game)  # Should not crash
