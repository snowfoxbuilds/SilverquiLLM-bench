"""Tests for SOS 22 — Interjection.

An instant for {W} that gives target creature +2/+2 and first strike
until end of turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_22.card_impl import Interjection
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestInterjectionProperties:
    """Static card data should match the SOS 22 spec."""

    def test_name(self) -> None:
        card = Interjection(owner=None)
        assert card.name == "Interjection"

    def test_is_instant(self) -> None:
        card = Interjection(owner=None)
        assert isinstance(card, Instant)

    def test_mana_cost(self) -> None:
        card = Interjection(owner=None)
        assert card.mana_cost == ManaCost.parse("{W}")


class TestInterjectionTargeting:
    """get_targets() should require a single creature target."""

    def test_returns_single_target_requirement(self) -> None:
        game = create_game()
        reqs = Interjection(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        req = Interjection(owner=None).get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        req = Interjection(owner=None).get_targets(game)[0]
        creature = Creature(name="Test Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True

    def test_target_filter_rejects_noncreature(self) -> None:
        game = create_game()
        req = Interjection(owner=None).get_targets(game)[0]
        non_creature = Creature(name="Not Creature")
        non_creature.card_types = set()
        assert req.filter_fn(non_creature) is False


class TestInterjectionResolution:
    """on_resolve applies +2/+2 and first strike until end of turn."""

    def test_grants_plus_two_plus_two(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = Interjection(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.get_power(game) == 4
        assert bear.get_toughness(game) == 4

    def test_grants_first_strike(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = Interjection(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert Keyword.FIRST_STRIKE in bear.keywords

    def test_no_target_is_noop(self) -> None:
        """Resolving with no valid target should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = Interjection(owner=p1, controller=p1)
        spell.on_resolve(game)  # should not raise
