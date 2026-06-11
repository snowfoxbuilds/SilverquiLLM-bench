"""Tests for SOS 47 — Essence Scatter.

Instant for {1}{U}. Counter target creature spell.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_47.card_impl import EssenceScatter
from engine.card import Instant, Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestEssenceScatterProperties:
    """Static card data should match the SOS 47 spec."""

    def test_is_instant(self) -> None:
        card = EssenceScatter(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = EssenceScatter(owner=None)
        assert card.name == "Essence Scatter"

    def test_mana_cost(self) -> None:
        card = EssenceScatter(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}")


class TestEssenceScatterCounters:
    """Counter target creature spell."""

    def test_counters_creature_spell(self) -> None:
        """A creature spell on the stack should be countered (moved to graveyard)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        target_creature.owner = p2
        target_creature.controller = p2
        scatter = EssenceScatter(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[scatter], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        # Put creature on the stack
        game.move_to_zone(target_creature, Zone.STACK)
        cast_spell(game, 0, "Essence Scatter", targets=[target_creature])
        # The creature should be in the graveyard, not the battlefield
        bf = game.get_battlefield(p2).get_all()
        assert target_creature not in bf
        gy = game.get_graveyard(p2).get_all()
        assert target_creature in gy

    def test_cannot_target_noncreature_spell(self) -> None:
        """Essence Scatter can only target creature spells."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        noncreature = Instant(name="Lightning Bolt")
        noncreature.owner = p2
        scatter = EssenceScatter(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[scatter], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        game.move_to_zone(noncreature, Zone.STACK)
        # Should not be a valid target
        assert not scatter.is_valid_target(game, noncreature)

    def test_scatter_goes_to_graveyard_after_resolving(self) -> None:
        """After resolving, Essence Scatter itself goes to the graveyard."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_creature = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        target_creature.owner = p2
        target_creature.controller = p2
        scatter = EssenceScatter(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[scatter], mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1})
        game.move_to_zone(target_creature, Zone.STACK)
        cast_spell(game, 0, "Essence Scatter", targets=[target_creature])
        gy = game.get_graveyard(p1).get_all()
        assert scatter in gy
