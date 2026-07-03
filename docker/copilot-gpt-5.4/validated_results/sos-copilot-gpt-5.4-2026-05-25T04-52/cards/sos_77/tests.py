"""Tests for SOS 77 — Cost of Brilliance."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_77.card_impl import CostOfBrilliance
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestCostOfBrillianceProperties:
    """Static card data should match the SOS 77 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(CostOfBrilliance(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = CostOfBrilliance(owner=None)
        assert card.name == "Cost of Brilliance"
        assert card.mana_cost == ManaCost.parse("{2}{B}")


class TestCostOfBrillianceTargeting:
    """Cost of Brilliance should target a player and up to one creature."""

    def test_returns_player_then_creature_target_requirements(self) -> None:
        game = create_game()
        reqs = CostOfBrilliance(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD

    def test_target_filters_accept_players_then_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = CostOfBrilliance(owner=p1, controller=p1)
        reqs = spell.get_targets(game)
        creature = Creature(name="Helpful Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert reqs[0].filter_fn(p1) is True
        assert reqs[0].filter_fn(p2) is True
        assert reqs[0].filter_fn(creature) is False
        assert reqs[1].filter_fn(creature) is True
        assert reqs[1].filter_fn(non_creature) is False
        assert reqs[1].filter_fn(p1) is False


class TestCostOfBrillianceResolution:
    """Cost of Brilliance should draw, drain, and optionally add a counter."""

    def test_on_resolve_target_player_draws_two_loses_two_and_target_creature_gets_a_counter(self) -> None:
        game = create_game()
        p1, p2 = game.players
        draw_one = CardImpl(name="First Insight", owner=p2, controller=p2)
        draw_two = CardImpl(name="Second Insight", owner=p2, controller=p2)
        target = Creature(
            name="Campus Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_library(p2).add(draw_one)
        game.get_library(p2).add(draw_two)
        game.get_battlefield(p1).add(target)

        spell = CostOfBrilliance(owner=p1, controller=p1)
        spell.chosen_targets = [p2, target]
        spell.on_resolve(game)

        assert game.get_hand(p2).contains(draw_one)
        assert game.get_hand(p2).contains(draw_two)
        assert p2.life == 18
        assert target.plus_one_counters == 1

    def test_on_resolve_allows_omitting_the_creature_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        draw_one = CardImpl(name="First Insight", owner=p2, controller=p2)
        draw_two = CardImpl(name="Second Insight", owner=p2, controller=p2)
        target = Creature(
            name="Untouched Assistant",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        game.get_library(p2).add(draw_one)
        game.get_library(p2).add(draw_two)
        game.get_battlefield(p1).add(target)

        spell = CostOfBrilliance(owner=p1, controller=p1)
        spell.chosen_targets = [p2, None]
        spell.on_resolve(game)

        assert game.get_hand(p2).contains(draw_one)
        assert game.get_hand(p2).contains(draw_two)
        assert p2.life == 18
        assert target.plus_one_counters == 0
