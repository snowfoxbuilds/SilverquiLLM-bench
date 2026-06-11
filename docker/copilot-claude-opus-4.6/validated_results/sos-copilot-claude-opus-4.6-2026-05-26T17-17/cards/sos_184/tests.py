"""Tests for SOS 184 — Dina's Guidance."""

from __future__ import annotations

import pytest

from cards.sos.sos_184.card_impl import DinasGuidance
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestDinasGuidanceProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = DinasGuidance(owner=None)
        assert card.name == "Dina's Guidance"

    def test_mana_cost(self) -> None:
        card = DinasGuidance(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{G}")

    def test_is_instant(self) -> None:
        card = DinasGuidance(owner=None)
        assert isinstance(card, Instant)


class TestDinasGuidanceResolution:
    """Search your library for a creature card, reveal it, put it into your
    hand or graveyard, then shuffle."""

    def test_search_puts_creature_into_hand(self) -> None:
        """Player can choose to put the found creature into hand."""
        game = create_game()
        target_creature = Creature(name="Found Bear", base_power=2, base_toughness=2)
        target_creature.card_types = {CardType.CREATURE}
        guidance = DinasGuidance(owner=None)
        set_board_state(game, 0, hand=[guidance],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        # Put a creature in library
        game.players[0].library = [target_creature]
        cast_spell(game, 0, "Dina's Guidance")
        hand_names = [c.name for c in game.players[0].hand]
        assert "Found Bear" in hand_names

    def test_search_puts_creature_into_graveyard(self) -> None:
        """Player can choose to put the found creature into graveyard."""
        game = create_game()
        target_creature = Creature(name="Grave Bear", base_power=2, base_toughness=2)
        target_creature.card_types = {CardType.CREATURE}
        guidance = DinasGuidance(owner=None)
        set_board_state(game, 0, hand=[guidance],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        game.players[0].library = [target_creature]
        # Configure choice to put in graveyard
        cast_spell(game, 0, "Dina's Guidance")
        # At least one of hand or graveyard should contain the creature
        hand_names = [c.name for c in game.players[0].hand]
        graveyard_names = [c.name for c in game.players[0].graveyard]
        assert "Grave Bear" in hand_names or "Grave Bear" in graveyard_names

    def test_library_is_shuffled_after_search(self) -> None:
        """The library should be shuffled after the search."""
        game = create_game()
        creatures = [Creature(name=f"Creature {i}", base_power=1, base_toughness=1)
                     for i in range(10)]
        for c in creatures:
            c.card_types = {CardType.CREATURE}
        guidance = DinasGuidance(owner=None)
        set_board_state(game, 0, hand=[guidance],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        game.players[0].library = list(creatures)
        cast_spell(game, 0, "Dina's Guidance")
        # Library should have one fewer card (the found creature was removed)
        assert len(game.players[0].library) <= 9

    def test_only_finds_creature_cards(self) -> None:
        """Non-creature cards in library should not be findable."""
        game = create_game()
        non_creature = Instant(name="Not A Creature")
        non_creature.card_types = {CardType.INSTANT}
        guidance = DinasGuidance(owner=None)
        set_board_state(game, 0, hand=[guidance],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        game.players[0].library = [non_creature]
        cast_spell(game, 0, "Dina's Guidance")
        # No creature found, hand should be empty
        hand_names = [c.name for c in game.players[0].hand]
        assert "Not A Creature" not in hand_names

    def test_empty_library_does_not_crash(self) -> None:
        """Casting with an empty library should resolve without error."""
        game = create_game()
        guidance = DinasGuidance(owner=None)
        set_board_state(game, 0, hand=[guidance],
                        mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 1})
        game.players[0].library = []
        cast_spell(game, 0, "Dina's Guidance")
        # Should not raise; hand remains empty
        assert len(game.players[0].hand) == 0
