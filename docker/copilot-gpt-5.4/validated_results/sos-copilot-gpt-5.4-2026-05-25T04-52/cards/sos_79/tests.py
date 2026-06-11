"""Tests for SOS 79 — Dissection Practice."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_79.card_impl import DissectionPractice
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestDissectionPracticeProperties:
    """Static card data should match the SOS 79 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(DissectionPractice(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = DissectionPractice(owner=None)
        assert card.name == "Dissection Practice"
        assert card.mana_cost == ManaCost.parse("{B}")


class TestDissectionPracticeTargeting:
    """Dissection Practice should target an opponent and up to two creatures."""

    def test_returns_opponent_then_two_creature_target_requirements(self) -> None:
        game = create_game()
        reqs = DissectionPractice(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 3
        assert all(isinstance(req, TargetRequirement) for req in reqs)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD
        assert reqs[2].zone == Zone.BATTLEFIELD

    def test_target_filters_accept_an_opponent_then_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = DissectionPractice(owner=p1, controller=p1)
        reqs = spell.get_targets(game)
        creature = Creature(name="Study Subject", base_power=2, base_toughness=2)
        non_creature = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert reqs[0].filter_fn(p2) is True
        assert reqs[0].filter_fn(p1) is False
        assert reqs[0].filter_fn(creature) is False
        assert reqs[1].filter_fn(creature) is True
        assert reqs[1].filter_fn(non_creature) is False
        assert reqs[2].filter_fn(creature) is True
        assert reqs[2].filter_fn(non_creature) is False


class TestDissectionPracticeResolution:
    """Dissection Practice should drain life and apply temporary stat changes."""

    def test_on_resolve_drains_life_and_applies_plus_one_plus_one_and_minus_one_minus_one(self) -> None:
        game = create_game()
        p1, p2 = game.players
        boosted = Creature(
            name="Boosted Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        shrunk = Creature(
            name="Shrunk Student",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        game.get_battlefield(p1).add(boosted)
        game.get_battlefield(p2).add(shrunk)

        spell = DissectionPractice(owner=p1, controller=p1)
        spell.chosen_targets = [p2, boosted, shrunk]
        spell.on_resolve(game)

        assert p1.life == 21
        assert p2.life == 19
        assert boosted.power == 3
        assert boosted.toughness == 3
        assert shrunk.power == 2
        assert shrunk.toughness == 2

    def test_temporary_stat_changes_expire_at_end_of_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        boosted = Creature(
            name="Boosted Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        shrunk = Creature(
            name="Shrunk Student",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        game.get_battlefield(p1).add(boosted)
        game.get_battlefield(p2).add(shrunk)

        spell = DissectionPractice(owner=p1, controller=p1)
        spell.chosen_targets = [p2, boosted, shrunk]
        spell.on_resolve(game)

        assert boosted.power == 3
        assert shrunk.power == 2

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert boosted.power == 2
        assert boosted.toughness == 2
        assert shrunk.power == 3
        assert shrunk.toughness == 3

    def test_on_resolve_allows_omitting_either_creature_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        boosted = Creature(
            name="Untouched Ally",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        shrunk = Creature(
            name="Untouched Enemy",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        game.get_battlefield(p1).add(boosted)
        game.get_battlefield(p2).add(shrunk)

        spell = DissectionPractice(owner=p1, controller=p1)
        spell.chosen_targets = [p2, None, None]
        spell.on_resolve(game)

        assert p1.life == 21
        assert p2.life == 19
        assert boosted.power == 2
        assert boosted.toughness == 2
        assert shrunk.power == 3
        assert shrunk.toughness == 3
