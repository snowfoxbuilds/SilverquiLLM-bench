"""Tests for sos_245 — Witherbloom, the Balancer."""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import create_game


class TestWitherbloomProperties:
    def test_name(self) -> None:
        assert WitherbloomTheBalancer(owner=None).name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        assert WitherbloomTheBalancer(owner=None).mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_is_creature(self) -> None:
        assert isinstance(WitherbloomTheBalancer(owner=None), Creature)

    def test_power_toughness(self) -> None:
        c = WitherbloomTheBalancer(owner=None)
        assert c.base_power == 5
        assert c.base_toughness == 5

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in WitherbloomTheBalancer(owner=None).keywords

    def test_has_deathtouch(self) -> None:
        assert Keyword.DEATHTOUCH in WitherbloomTheBalancer(owner=None).keywords

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in WitherbloomTheBalancer(owner=None).supertypes

    def test_has_dragon_subtype(self) -> None:
        assert "Dragon" in WitherbloomTheBalancer(owner=None).subtypes


class TestWitherbloomAffinity:
    """Witherbloom has affinity for creatures: costs {1} less for each creature you control."""

    def test_cost_reduction_zero_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        # No creatures on battlefield — no cost reduction
        assert wb.cost_reduction(game) == 0

    def test_cost_reduction_one_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Add one creature to battlefield (not Witherbloom itself)
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        assert wb.cost_reduction(game) == 1

    def test_cost_reduction_multiple_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        for i in range(4):
            c = Creature(name=f"Creature {i}", base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)
        assert wb.cost_reduction(game) == 4

    def test_cost_reduction_opponent_creatures_dont_count(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Add creatures to opponent's battlefield
        bear = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(bear)
        assert wb.cost_reduction(game) == 0


class TestWitherbloomGrantsAffinity:
    """Instants and sorceries you cast have affinity for creatures (same reduction)."""

    def test_instant_gets_creature_affinity(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wb)

        instant = Instant(
            name="Test Instant", mana_cost=ManaCost.parse("{5}"),
            owner=p1, controller=p1,
        )

        # Put 2 creatures on battlefield (Witherbloom + 2 = 3 total)
        for i in range(2):
            c = Creature(name=f"Creature {i}", base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)

        # get_cost_reduction checks both card.cost_reduction AND battlefield grants
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, instant, p1)
        # 3 creatures (wb + 2 bears) → 3 reduction (capped at generic cost 5)
        assert reduction == 3

    def test_sorcery_gets_creature_affinity(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wb)

        sorcery = Sorcery(
            name="Test Sorcery", mana_cost=ManaCost.parse("{4}"),
            owner=p1, controller=p1,
        )

        # 3 additional creatures + Witherbloom = 4 total
        for i in range(3):
            c = Creature(name=f"C{i}", base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)

        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, sorcery, p1)
        # 4 creatures → 4 reduction (capped at generic cost 4)
        assert reduction == 4

    def test_no_affinity_without_witherbloom(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # No Witherbloom on battlefield
        instant = Instant(
            name="Test Instant", mana_cost=ManaCost.parse("{5}"),
            owner=p1, controller=p1,
        )
        for i in range(3):
            c = Creature(name=f"C{i}", base_power=1, base_toughness=1, owner=p1, controller=p1)
            game.get_battlefield(p1).add(c)

        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, instant, p1)
        # No Witherbloom → no affinity grant
        assert reduction == 0

    def test_witherbloom_counts_itself_for_own_casting(self) -> None:
        """Witherbloom counts itself as a creature when computing its own cost reduction."""
        game = create_game()
        p1 = game.players[0]
        wb = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Add Witherbloom to battlefield (it will count itself)
        game.get_battlefield(p1).add(wb)
        # 1 creature (wb itself) on battlefield
        assert wb.cost_reduction(game) == 1
