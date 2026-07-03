"""Tests for SOS 41 — Chase Inspiration.

Chase Inspiration is a {U} instant that gives a target creature you control
+0/+3 and hexproof until end of turn.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_41.card_impl import ChaseInspiration
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state, cast_spell


class TestChaseInspirationProperties:
    """Static card data should match the SOS 41 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ChaseInspiration(owner=None), Instant)

    def test_name(self) -> None:
        assert ChaseInspiration(owner=None).name == "Chase Inspiration"

    def test_mana_cost(self) -> None:
        assert ChaseInspiration(owner=None).mana_cost == ManaCost.parse("{U}")


class TestChaseInspirationTargeting:
    """get_targets() requires a creature you control."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = ChaseInspiration(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = ChaseInspiration(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_own_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ChaseInspiration(owner=p1, controller=p1)
        req = spell.get_targets(game)[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        assert req.filter_fn(bear) is True

    def test_target_filter_rejects_opponent_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        spell = ChaseInspiration(owner=p1, controller=p1)
        req = spell.get_targets(game)[0]
        enemy = Creature(name="Enemy", owner=p2, controller=p2, base_power=2, base_toughness=2)
        enemy.card_types = {CardType.CREATURE}
        assert req.filter_fn(enemy) is False


class TestChaseInspirationResolution:
    """on_resolve gives +0/+3 and hexproof until end of turn."""

    def test_toughness_boost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = ChaseInspiration(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.get_toughness(game) >= 5  # 2 base + 3 boost

    def test_power_unchanged(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = ChaseInspiration(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.get_power(game) == 2

    def test_gains_hexproof(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = ChaseInspiration(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert Keyword.HEXPROOF in bear.keywords

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ChaseInspiration(owner=p1, controller=p1)
        # No chosen_targets — should not raise
        spell.on_resolve(game)
