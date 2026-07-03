"""Tests for SOS 53 — Homesickness."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_53.card_impl import Homesickness
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestHomesicknessProperties:
    """Static card data should match the SOS 53 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Homesickness(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = Homesickness(owner=None)
        assert card.name == "Homesickness"
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")


class TestHomesicknessTargeting:
    """Homesickness should target a player and up to two creatures."""

    def test_returns_player_and_two_creature_target_requirements(self) -> None:
        game = create_game()
        reqs = Homesickness(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 3
        assert all(isinstance(req, TargetRequirement) for req in reqs)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD
        assert reqs[2].zone == Zone.BATTLEFIELD

    def test_target_filters_accept_players_then_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        reqs = Homesickness(owner=p1, controller=p1).get_targets(game)
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Hall")

        assert reqs[0].filter_fn(p1) is True
        assert reqs[0].filter_fn(creature) is False
        assert reqs[1].filter_fn(creature) is True
        assert reqs[1].filter_fn(non_creature) is False
        assert reqs[2].filter_fn(creature) is True
        assert reqs[2].filter_fn(non_creature) is False


class TestHomesicknessResolution:
    """Homesickness should draw cards for the player target and tap/stun creature targets."""

    def test_on_resolve_draws_two_and_taps_and_stuns_up_to_two_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        draw_one = CardImpl(name="First Insight", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Insight", owner=p1, controller=p1)
        target_one = Creature(name="Target One", owner=p2, controller=p2, base_power=2, base_toughness=2)
        target_two = Creature(name="Target Two", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        game.get_battlefield(p2).add(target_one)
        game.get_battlefield(p2).add(target_two)

        spell = Homesickness(owner=p1, controller=p1)
        spell.chosen_targets = [p1, target_one, target_two]
        spell.on_resolve(game)

        assert game.get_hand(p1).contains(draw_one)
        assert game.get_hand(p1).contains(draw_two)
        assert target_one.is_tapped is True
        assert target_two.is_tapped is True
        assert getattr(target_one, "counters", {}).get("stun", 0) == 1
        assert getattr(target_two, "counters", {}).get("stun", 0) == 1

    def test_on_resolve_allows_fewer_than_two_creature_targets(self) -> None:
        game = create_game()
        p1, p2 = game.players
        draw_one = CardImpl(name="First Insight", owner=p1, controller=p1)
        draw_two = CardImpl(name="Second Insight", owner=p1, controller=p1)
        target = Creature(name="Target One", owner=p2, controller=p2, base_power=2, base_toughness=2)
        untouched = Creature(name="Untouched", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_library(p1).add(draw_one)
        game.get_library(p1).add(draw_two)
        game.get_battlefield(p2).add(target)
        game.get_battlefield(p2).add(untouched)

        spell = Homesickness(owner=p1, controller=p1)
        spell.chosen_targets = [p1, target, None]
        spell.on_resolve(game)

        assert game.get_hand(p1).contains(draw_one)
        assert game.get_hand(p1).contains(draw_two)
        assert target.is_tapped is True
        assert getattr(target, "counters", {}).get("stun", 0) == 1
        assert untouched.is_tapped is False
        assert getattr(untouched, "counters", {}).get("stun", 0) == 0
