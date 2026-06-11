"""Tests for SOS 34 — Stand Up for Yourself."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_34.card_impl import StandUpForYourself
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestStandUpForYourselfProperties:
    """Static card data should match the SOS 34 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(StandUpForYourself(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = StandUpForYourself(owner=None)
        assert card.name == "Stand Up for Yourself"
        assert card.mana_cost == ManaCost.parse("{2}{W}")


class TestStandUpForYourselfTargeting:
    """Stand Up for Yourself should only target creatures with power 3 or greater."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = StandUpForYourself(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_only_creatures_with_power_three_or_greater(self) -> None:
        game = create_game()
        req = StandUpForYourself(owner=None).get_targets(game)[0]

        qualifying_creature = Creature(name="Hill Giant", base_power=3, base_toughness=3)
        small_creature = Creature(name="Bear Cub", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes")

        assert req.filter_fn(qualifying_creature) is True
        assert req.filter_fn(small_creature) is False
        assert req.filter_fn(non_creature) is False


class TestStandUpForYourselfResolution:
    """Stand Up for Yourself should destroy only qualifying targets."""

    def test_destroys_target_creature_with_power_three_or_greater(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Hill Giant",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        spell = StandUpForYourself(owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_graveyard(p2).contains(target)

    def test_does_not_destroy_creatures_below_the_power_threshold(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Bear Cub",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = StandUpForYourself(owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        assert game.get_battlefield(p2).contains(target)
        assert not game.get_graveyard(p2).contains(target)

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = StandUpForYourself(owner=p1, controller=p1)

        spell.on_resolve(game)

        assert game.get_graveyard(p1).get_all() == []
        assert game.get_graveyard(p2).get_all() == []
