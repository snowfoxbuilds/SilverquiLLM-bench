"""Tests for SOS 136 — Unsubtle Mockery."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_136.card_impl import UnsubtleMockery
from benchmarks.sos.workspace.engine.card import Artifact, CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestUnsubtleMockeryProperties:
    """Static card data should match the SOS 136 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(UnsubtleMockery(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = UnsubtleMockery(owner=None)
        assert card.name == "Unsubtle Mockery"
        assert card.mana_cost == ManaCost.parse("{2}{R}")


class TestUnsubtleMockeryTargeting:
    """Unsubtle Mockery should target a creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = UnsubtleMockery(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = UnsubtleMockery(owner=None).get_targets(game)[0]
        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        noncreature = Artifact(name="Lecture Relic")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(noncreature) is False


class TestUnsubtleMockeryResolution:
    """Unsubtle Mockery should deal 4 damage and surveil 1."""

    def test_on_resolve_deals_four_damage_and_may_put_the_surveilled_card_into_your_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Large Assistant",
            owner=p2,
            controller=p2,
            base_power=5,
            base_toughness=5,
        )
        bottom_card = CardImpl(name="Earlier Note", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Note", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(True)

        spell = UnsubtleMockery(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 4
        assert game.get_graveyard(p1).contains(top_card)
        assert game.get_library(p1).top(1) == [bottom_card]

    def test_on_resolve_can_leave_the_surveilled_card_on_top_of_your_library(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Study Dummy",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bottom_card = CardImpl(name="Earlier Note", owner=p1, controller=p1)
        top_card = CardImpl(name="Latest Note", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_library(p1).add(bottom_card)
        game.get_library(p1).add(top_card)
        p1._script.append(False)

        spell = UnsubtleMockery(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 4
        assert game.get_graveyard(p1).get_all() == []
        assert game.get_library(p1).get_all() == [bottom_card, top_card]
