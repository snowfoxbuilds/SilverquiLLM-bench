"""Tests for SOS 118 — Heated Argument."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_118.card_impl import HeatedArgument
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestHeatedArgumentProperties:
    """Static card data should match the SOS 118 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(HeatedArgument(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = HeatedArgument(owner=None)

        assert card.name == "Heated Argument"
        assert card.mana_cost == ManaCost.parse("{4}{R}")


class TestHeatedArgumentTargeting:
    """Heated Argument should target a single creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = HeatedArgument(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = HeatedArgument(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(non_creature) is False


class TestHeatedArgumentResolution:
    """Heated Argument should damage the target and optionally its controller."""

    def test_on_resolve_deals_six_damage_to_target_creature_when_you_decline_to_exile(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Study Bear",
            owner=p2,
            controller=p2,
            base_power=6,
            base_toughness=6,
        )
        fodder = CardImpl(name="Spent Notes", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_graveyard(p1).add(fodder)
        p1._script.append(False)

        spell = HeatedArgument(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 6
        assert p2.life == 20
        assert game.get_graveyard(p1).contains(fodder)
        assert not game.get_exile(p1).contains(fodder)

    def test_exiling_a_graveyard_card_deals_two_damage_to_that_creatures_controller(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Borrowed Bear",
            owner=p1,
            controller=p2,
            base_power=6,
            base_toughness=6,
        )
        fodder = CardImpl(name="Spent Notes", owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_graveyard(p1).add(fodder)
        p1._script.extend([True, fodder])

        spell = HeatedArgument(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 6
        assert p2.life == 18
        assert not game.get_graveyard(p1).contains(fodder)
        assert game.get_exile(p1).contains(fodder)
