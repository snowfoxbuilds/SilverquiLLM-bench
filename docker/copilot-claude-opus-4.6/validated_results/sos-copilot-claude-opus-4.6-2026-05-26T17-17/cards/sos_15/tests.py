"""Tests for SOS 15 — Erode.

Instant for {W}.
Destroy target creature or planeswalker. Its controller may search their
library for a basic land card, put it onto the battlefield tapped, then shuffle.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_15.card_impl import Erode
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestErodeProperties:
    """Static card data should match the SOS 15 spec."""

    def test_is_instant(self) -> None:
        card = Erode(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert Erode(owner=None).name == "Erode"

    def test_mana_cost(self) -> None:
        assert Erode(owner=None).mana_cost == ManaCost.parse("{W}")


class TestErodeTargeting:
    """Targets a creature or planeswalker."""

    def test_has_target_requirement(self) -> None:
        game = create_game()
        card = Erode(owner=None)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) >= 1

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        card = Erode(owner=None)
        reqs = card.get_targets(game)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_accepts_creature(self) -> None:
        game = create_game()
        card = Erode(owner=None)
        req = card.get_targets(game)[0]
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        assert req.filter_fn(creature) is True


class TestErodeResolution:
    """Destroy target; controller may search for basic land."""

    def test_destroys_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = Erode(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        # Target should no longer be on the battlefield
        bf = game.get_battlefield(p2)
        assert target not in bf.get_all()

    def test_destroyed_creature_goes_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(
            name="Grizzly Bears", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        spell = Erode(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        gy = game.get_graveyard(p2)
        assert target in gy.get_all()

    def test_no_target_is_noop(self) -> None:
        """If chosen_targets is empty/unset, resolution doesn't crash."""
        game = create_game()
        p1 = game.players[0]
        spell = Erode(owner=p1, controller=p1)
        # No target set - should not raise
        spell.on_resolve(game)
