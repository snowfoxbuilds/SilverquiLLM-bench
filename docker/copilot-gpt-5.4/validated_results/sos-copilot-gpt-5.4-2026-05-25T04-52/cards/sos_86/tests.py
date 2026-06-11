"""Tests for SOS 86 — Last Gasp."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_86.card_impl import LastGasp
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestLastGaspProperties:
    """Static card data should match the SOS 86 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(LastGasp(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = LastGasp(owner=None)
        assert card.name == "Last Gasp"
        assert card.mana_cost == ManaCost.parse("{1}{B}")


class TestLastGaspTargeting:
    """Last Gasp should target a single creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = LastGasp(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = LastGasp(owner=None).get_targets(game)[0]
        creature = Creature(name="Study Bear", base_power=5, base_toughness=5)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestLastGaspResolution:
    """Last Gasp should give the target -3/-3 until end of turn."""

    def test_target_gets_minus_three_minus_three(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Sturdy Assistant",
            owner=p1,
            controller=p1,
            base_power=5,
            base_toughness=5,
        )
        game.get_battlefield(p1).add(target)
        card = LastGasp(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)

        assert target.power == 2
        assert target.toughness == 2

    def test_temporary_stat_reduction_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Sturdy Assistant",
            owner=p1,
            controller=p1,
            base_power=5,
            base_toughness=5,
        )
        game.get_battlefield(p1).add(target)
        card = LastGasp(owner=p1, controller=p1)
        card.chosen_targets = [target]

        card.on_resolve(game)
        assert target.power == 2
        assert target.toughness == 2

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 5
        assert target.toughness == 5
