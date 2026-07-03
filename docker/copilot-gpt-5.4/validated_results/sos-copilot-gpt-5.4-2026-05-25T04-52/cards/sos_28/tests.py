"""Tests for SOS 28 — Rapier Wit."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_28.card_impl import RapierWit
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.game import untap
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestRapierWitProperties:
    """Static card data should match the SOS 28 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(RapierWit(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = RapierWit(owner=None)
        assert card.name == "Rapier Wit"
        assert card.mana_cost == ManaCost.parse("{1}{W}")


class TestRapierWitTargeting:
    """Rapier Wit should target a creature on the battlefield."""

    def test_returns_single_creature_target_requirement(self) -> None:
        game = create_game()
        reqs = RapierWit(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = RapierWit(owner=None).get_targets(game)[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Hall")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestRapierWitResolution:
    """Rapier Wit should tap its target, conditionally stun it, and draw a card."""

    def test_on_resolve_during_your_turn_taps_the_target_adds_a_stun_counter_and_draws_a_card(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Opponent Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Fresh Insight", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_library(p1).add(drawn)
        game.active_player_index = 0

        spell = RapierWit(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.is_tapped is True
        assert getattr(target, "counters", {}).get("stun", 0) == 1
        assert game.get_hand(p1).contains(drawn)

    def test_stun_counter_is_consumed_instead_of_untapping_the_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Opponent Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(target)
        game.active_player_index = 0

        spell = RapierWit(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        first_untap = untap(game, target)

        assert first_untap is False
        assert target.is_tapped is True
        assert getattr(target, "counters", {}).get("stun", 0) == 0

        second_untap = untap(game, target)

        assert second_untap is True
        assert target.is_tapped is False

    def test_on_resolve_during_an_opponents_turn_taps_the_target_without_adding_a_stun_counter_and_still_draws(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Opponent Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        drawn = CardImpl(name="Fresh Insight", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_library(p1).add(drawn)
        game.active_player_index = 1

        spell = RapierWit(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.is_tapped is True
        assert getattr(target, "counters", {}).get("stun", 0) == 0
        assert game.get_hand(p1).contains(drawn)
