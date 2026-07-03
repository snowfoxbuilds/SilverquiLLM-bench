"""Tests for SOS 34 — Stand Up for Yourself.

Instant for {2}{W}: Destroy target creature with power 3 or greater.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_34.card_impl import StandUpForYourself
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestStandUpForYourselfProperties:
    """Static card data should match the SOS 34 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(StandUpForYourself(owner=None), Instant)

    def test_name(self) -> None:
        assert StandUpForYourself(owner=None).name == "Stand Up for Yourself"

    def test_mana_cost(self) -> None:
        assert StandUpForYourself(owner=None).mana_cost == ManaCost.parse("{2}{W}")


class TestStandUpForYourselfTargeting:
    """Targeting: creature with power 3 or greater."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = StandUpForYourself(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_filter_accepts_power_3_creature(self) -> None:
        game = create_game()
        req = StandUpForYourself(owner=None).get_targets(game)[0]

        big = Creature(name="Big Beast", base_power=3, base_toughness=3)
        big.card_types = {CardType.CREATURE}
        assert req.filter_fn(big) is True

    def test_target_filter_accepts_power_5_creature(self) -> None:
        game = create_game()
        req = StandUpForYourself(owner=None).get_targets(game)[0]

        huge = Creature(name="Huge Beast", base_power=5, base_toughness=5)
        huge.card_types = {CardType.CREATURE}
        assert req.filter_fn(huge) is True

    def test_target_filter_rejects_power_2_creature(self) -> None:
        game = create_game()
        req = StandUpForYourself(owner=None).get_targets(game)[0]

        small = Creature(name="Small Bear", base_power=2, base_toughness=2)
        small.card_types = {CardType.CREATURE}
        assert req.filter_fn(small) is False

    def test_target_filter_rejects_power_0_creature(self) -> None:
        game = create_game()
        req = StandUpForYourself(owner=None).get_targets(game)[0]

        wall = Creature(name="Wall", base_power=0, base_toughness=5)
        wall.card_types = {CardType.CREATURE}
        assert req.filter_fn(wall) is False


class TestStandUpForYourselfResolution:
    """On resolve, destroy the target creature."""

    def test_destroys_target_creature_with_power_3(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = StandUpForYourself(owner=p1, controller=p1)
        big = Creature(name="Big Beast", base_power=3, base_toughness=3,
                       owner=p2, controller=p2)
        big.card_types = {CardType.CREATURE}
        big.zone = Zone.BATTLEFIELD
        game.get_battlefield(p2).add(big)

        spell.chosen_targets = [big]
        spell.on_resolve(game)

        assert big not in game.get_battlefield(p2)

    def test_destroys_target_creature_with_power_greater_than_3(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = StandUpForYourself(owner=p1, controller=p1)
        huge = Creature(name="Huge Beast", base_power=7, base_toughness=7,
                        owner=p2, controller=p2)
        huge.card_types = {CardType.CREATURE}
        huge.zone = Zone.BATTLEFIELD
        game.get_battlefield(p2).add(huge)

        spell.chosen_targets = [huge]
        spell.on_resolve(game)

        assert huge not in game.get_battlefield(p2)

    def test_no_target_is_noop(self) -> None:
        """Resolution with no chosen targets should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = StandUpForYourself(owner=p1, controller=p1)
        spell.on_resolve(game)
