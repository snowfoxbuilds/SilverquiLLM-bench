"""Tests for SOS 193 — Growth Curve."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_193.card_impl import GrowthCurve
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestGrowthCurveProperties:
    """Static card data should match the SOS 193 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(GrowthCurve(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = GrowthCurve(owner=None)

        assert card.name == "Growth Curve"
        assert card.mana_cost == ManaCost.parse("{G}{U}")


class TestGrowthCurveTargeting:
    """Growth Curve should target only a creature you control."""

    def test_returns_a_single_battlefield_target_requirement_for_a_creature_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = GrowthCurve(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        friendly = Creature(name="Friendly Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        opposing = Creature(name="Opposing Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        noncreature = CardImpl(name="Lecture Hall")

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[0].filter_fn(friendly) is True
        assert reqs[0].filter_fn(opposing) is False
        assert reqs[0].filter_fn(noncreature) is False


class TestGrowthCurveResolution:
    """Growth Curve should add a counter, then double the total counters."""

    def test_on_resolve_puts_two_counters_on_a_creature_with_no_existing_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Vanilla Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = GrowthCurve(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.plus_one_counters == 2
        assert target.power == 4
        assert target.toughness == 4

    def test_on_resolve_turns_two_existing_plus_one_plus_one_counters_into_six(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Growing Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        target.plus_one_counters = 2
        target._base_plus_one_counters = 2
        spell = GrowthCurve(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert target.plus_one_counters == 6
        assert target.power == 8
        assert target.toughness == 8
