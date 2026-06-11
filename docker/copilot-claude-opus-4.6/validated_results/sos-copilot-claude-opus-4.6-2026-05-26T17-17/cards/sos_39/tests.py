"""Tests for SOS 39 — Brush Off.

Instant for {2}{U}{U}. Counter target spell.
Costs {1}{U} less if it targets an instant or sorcery spell.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_39.card_impl import BrushOff
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestBrushOffProperties:
    """Static card data should match the SOS 39 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(BrushOff(owner=None), Instant)

    def test_name(self) -> None:
        assert BrushOff(owner=None).name == "Brush Off"

    def test_mana_cost(self) -> None:
        assert BrushOff(owner=None).mana_cost == ManaCost.parse("{2}{U}{U}")


class TestBrushOffCostReduction:
    """Costs {1}{U} less when targeting an instant or sorcery spell."""

    def test_cost_reduction_targeting_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = BrushOff(owner=p1, controller=p1)
        # Simulate targeting an instant spell
        target_instant = Instant(name="Lightning Bolt", owner=p1)
        target_instant.card_types = {CardType.INSTANT}
        spell.chosen_targets = [target_instant]
        reduction = spell.cost_reduction(game)
        # Should reduce by 2 total (1 generic + 1 blue)
        assert reduction >= 2

    def test_no_cost_reduction_targeting_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = BrushOff(owner=p1, controller=p1)
        # Simulate targeting a creature spell
        target_creature = Creature(
            name="Bear", owner=p1, base_power=2, base_toughness=2
        )
        target_creature.card_types = {CardType.CREATURE}
        spell.chosen_targets = [target_creature]
        reduction = spell.cost_reduction(game)
        assert reduction == 0

    def test_cost_reduction_targeting_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = BrushOff(owner=p1, controller=p1)
        target_sorcery = Sorcery(name="Divination", owner=p1)
        target_sorcery.card_types = {CardType.SORCERY}
        spell.chosen_targets = [target_sorcery]
        reduction = spell.cost_reduction(game)
        assert reduction >= 2


class TestBrushOffTargeting:
    """Targets a spell (on the stack)."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        reqs = BrushOff(owner=None).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_stack(self) -> None:
        game = create_game()
        req = BrushOff(owner=None).get_targets(game)[0]
        assert req.zone == Zone.STACK


class TestBrushOffResolution:
    """on_resolve counters the target spell."""

    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Create a spell on the stack
        target_spell = Instant(name="Target Spell", owner=p2, controller=p2)
        target_spell.card_types = {CardType.INSTANT}

        spell = BrushOff(owner=p1, controller=p1)
        spell.chosen_targets = [target_spell]
        spell.on_resolve(game)

        # Target spell should be countered (moved to graveyard)
        graveyard = game.get_graveyard(p2)
        assert target_spell in graveyard

    def test_no_target_is_noop(self) -> None:
        """If target is gone, resolution should not raise."""
        game = create_game()
        p1 = game.players[0]
        spell = BrushOff(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)
