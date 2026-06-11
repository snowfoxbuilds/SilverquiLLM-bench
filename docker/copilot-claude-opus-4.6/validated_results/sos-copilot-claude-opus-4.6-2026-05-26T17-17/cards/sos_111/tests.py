"""Tests for SOS 111 — Choreographed Sparks."""

from __future__ import annotations

import pytest

from cards.sos.sos_111.card_impl import ChoreographedSparks
from engine.card import Creature, Instant
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestChoreographedSparksProperties:
    """Static card data should match spec."""

    def test_is_instant(self) -> None:
        card = ChoreographedSparks(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        assert ChoreographedSparks(owner=None).name == "Choreographed Sparks"

    def test_mana_cost(self) -> None:
        assert ChoreographedSparks(owner=None).mana_cost == ManaCost.parse("{R}{R}")


class TestChoreographedSparksCantBeCopied:
    """The spell itself cannot be copied."""

    def test_cant_be_copied_flag(self) -> None:
        card = ChoreographedSparks(owner=None)
        assert card.cant_be_copied is True


class TestChoreographedSparksModeSelection:
    """Choose one or both — copy instant/sorcery or copy creature spell."""

    def test_can_choose_instant_sorcery_mode(self) -> None:
        """Mode 1: Copy target instant or sorcery spell you control."""
        game = create_game()
        p1 = game.players[0]
        card = ChoreographedSparks(owner=p1, controller=p1)
        # Card should expose modes for selection
        modes = card.get_modes(game)
        assert len(modes) >= 2

    def test_can_choose_creature_mode(self) -> None:
        """Mode 2: Copy target creature spell you control."""
        game = create_game()
        p1 = game.players[0]
        card = ChoreographedSparks(owner=p1, controller=p1)
        modes = card.get_modes(game)
        # Should have at least the creature-copy mode
        assert any("creature" in m.lower() for m in modes)

    def test_can_choose_both_modes(self) -> None:
        """'Choose one or both' allows selecting both modes."""
        game = create_game()
        p1 = game.players[0]
        card = ChoreographedSparks(owner=p1, controller=p1)
        # min_modes should be 1, max_modes should be 2
        assert card.min_modes == 1
        assert card.max_modes == 2


class TestChoreographedSparksCreatureCopy:
    """Creature copy gains haste and end-step sacrifice."""

    def test_creature_copy_has_haste(self) -> None:
        """The token copy of a creature spell should gain haste."""
        game = create_game()
        p1 = game.players[0]
        card = ChoreographedSparks(owner=p1, controller=p1)

        # Create a creature spell on the stack to target
        target_creature = Creature(
            name="Test Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        target_creature.zone = Zone.STACK

        card.chosen_modes = [1]  # creature mode
        card.chosen_targets = [target_creature]
        card.on_resolve(game)

        # Find the token copy on the battlefield
        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if c.is_token and c.name == "Test Bear"]
        assert len(tokens) == 1
        from engine.types import Keyword
        assert Keyword.HASTE in tokens[0].keywords

    def test_creature_copy_sacrificed_at_end_step(self) -> None:
        """The token copy has 'At end step, sacrifice this token.'"""
        game = create_game()
        p1 = game.players[0]
        card = ChoreographedSparks(owner=p1, controller=p1)

        target_creature = Creature(
            name="Test Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        target_creature.zone = Zone.STACK

        card.chosen_modes = [1]  # creature mode
        card.chosen_targets = [target_creature]
        card.on_resolve(game)

        battlefield = game.get_battlefield(p1)
        tokens = [c for c in battlefield.cards if c.is_token and c.name == "Test Bear"]
        assert len(tokens) == 1
        assert tokens[0].sacrifice_at_end_step is True
