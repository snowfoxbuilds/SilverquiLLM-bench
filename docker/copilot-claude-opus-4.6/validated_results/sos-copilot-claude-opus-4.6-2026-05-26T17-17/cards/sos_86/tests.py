"""Tests for SOS 86 — Last Gasp.

Last Gasp is {1}{B} Instant: Target creature gets -3/-3 until end of turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_86.card_impl import LastGasp
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestLastGaspProperties:
    """Static card data should match the SOS 86 spec."""

    def test_is_instant(self) -> None:
        card = LastGasp(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert LastGasp(owner=None).name == "Last Gasp"

    def test_mana_cost(self) -> None:
        assert LastGasp(owner=None).mana_cost == ManaCost.parse("{1}{B}")


class TestLastGaspTargeting:
    """get_targets() should require a single creature target."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = LastGasp(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1

    def test_target_zone_is_battlefield(self) -> None:
        from engine.types import TargetRequirement
        game = create_game()
        req = LastGasp(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        req = LastGasp(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestLastGaspResolution:
    """on_resolve gives target creature -3/-3 until end of turn."""

    def test_reduces_power_and_toughness(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Hill Giant",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = LastGasp(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.power == 0
        assert target.toughness == 0

    def test_kills_small_creature(self) -> None:
        """A 2/2 creature should die (toughness <= 0) after -3/-3."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = LastGasp(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        # Toughness should be -1 (creature would die to SBA)
        assert target.toughness <= 0

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = LastGasp(owner=p1, controller=p1)
        # No chosen_targets — should not raise
        spell.on_resolve(game)
