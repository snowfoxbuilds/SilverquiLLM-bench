"""Tests for SOS 104 — Wander Off.

An instant for {3}{B} that exiles target creature.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_104.card_impl import WanderOff
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class TestWanderOffProperties:
    """Static card data should match the SOS 104 spec."""

    def test_is_instant(self) -> None:
        card = WanderOff(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert WanderOff(owner=None).name == "Wander Off"

    def test_mana_cost(self) -> None:
        assert WanderOff(owner=None).mana_cost == ManaCost.parse("{3}{B}")


class TestWanderOffTargeting:
    """get_targets() should require a creature target on the battlefield."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = WanderOff(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = WanderOff(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        req = WanderOff(owner=None).get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestWanderOffResolution:
    """on_resolve exiles the targeted creature."""

    def test_target_creature_is_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        bear = Creature(
            name="Grizzly Bears",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(bear)

        spell = WanderOff(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Bear should no longer be on the battlefield
        bf = game.get_battlefield(p2)
        assert bear not in bf.get_all()

        # Bear should be in exile
        exile = game.get_zone(p2, Zone.EXILE)
        assert bear in exile.get_all()

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = WanderOff(owner=p1, controller=p1)
        # No chosen_targets — should not raise
        spell.on_resolve(game)
