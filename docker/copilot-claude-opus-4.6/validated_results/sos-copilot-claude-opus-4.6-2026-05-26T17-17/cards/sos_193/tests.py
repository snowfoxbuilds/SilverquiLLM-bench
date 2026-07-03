"""Tests for SOS 193 — Growth Curve."""

from __future__ import annotations

import pytest

from cards.sos.sos_193.card_impl import GrowthCurve
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestGrowthCurveProperties:
    """Static card data should match SOS 193 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(GrowthCurve(owner=None), Sorcery)

    def test_name(self) -> None:
        assert GrowthCurve(owner=None).name == "Growth Curve"

    def test_mana_cost(self) -> None:
        assert GrowthCurve(owner=None).mana_cost == ManaCost.parse("{G}{U}")


class TestGrowthCurveTargeting:
    """Targeting: target creature you control."""

    def test_requires_target(self) -> None:
        game = create_game()
        reqs = GrowthCurve(owner=game.players[0]).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = GrowthCurve(owner=game.players[0]).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD


class TestGrowthCurveEffect:
    """Put a +1/+1 counter then double +1/+1 counters."""

    def test_creature_with_no_counters_gets_two(self) -> None:
        """0 counters + 1 = 1, then doubled = 2."""
        game = create_game()
        target = Creature(name="Test Bear", base_power=2, base_toughness=2)
        target.owner = game.players[0]
        spell = GrowthCurve(owner=game.players[0])
        set_board_state(game, 0, hand=[spell], battlefield=[target],
                        mana={ManaType.GREEN: 1, ManaType.BLUE: 1})

        cast_spell(game, 0, "Growth Curve", targets=[target])

        # 0 + 1 = 1, then doubled = 2 counters
        assert target.counters.get("+1/+1", 0) == 2

    def test_creature_with_existing_counters(self) -> None:
        """3 counters + 1 = 4, then doubled = 8."""
        game = create_game()
        target = Creature(name="Big Bear", base_power=2, base_toughness=2)
        target.owner = game.players[0]
        target.counters = {"+1/+1": 3}
        spell = GrowthCurve(owner=game.players[0])
        set_board_state(game, 0, hand=[spell], battlefield=[target],
                        mana={ManaType.GREEN: 1, ManaType.BLUE: 1})

        cast_spell(game, 0, "Growth Curve", targets=[target])

        # 3 + 1 = 4, then doubled = 8 counters
        assert target.counters.get("+1/+1", 0) == 8

    def test_creature_with_one_counter(self) -> None:
        """1 counter + 1 = 2, then doubled = 4."""
        game = create_game()
        target = Creature(name="Pumped Bear", base_power=2, base_toughness=2)
        target.owner = game.players[0]
        target.counters = {"+1/+1": 1}
        spell = GrowthCurve(owner=game.players[0])
        set_board_state(game, 0, hand=[spell], battlefield=[target],
                        mana={ManaType.GREEN: 1, ManaType.BLUE: 1})

        cast_spell(game, 0, "Growth Curve", targets=[target])

        # 1 + 1 = 2, then doubled = 4 counters
        assert target.counters.get("+1/+1", 0) == 4

    def test_power_toughness_reflect_counters(self) -> None:
        """After resolution, P/T should include counter bonuses."""
        game = create_game()
        target = Creature(name="Small Bear", base_power=1, base_toughness=1)
        target.owner = game.players[0]
        spell = GrowthCurve(owner=game.players[0])
        set_board_state(game, 0, hand=[spell], battlefield=[target],
                        mana={ManaType.GREEN: 1, ManaType.BLUE: 1})

        cast_spell(game, 0, "Growth Curve", targets=[target])

        # Base 1/1 + 2 counters = 3/3
        assert target.power == 3
        assert target.toughness == 3
