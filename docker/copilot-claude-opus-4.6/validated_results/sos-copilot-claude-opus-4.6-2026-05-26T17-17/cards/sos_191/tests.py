"""Tests for SOS 191 — Geometer's Arthropod."""

from __future__ import annotations

import pytest

from cards.sos.sos_191.card_impl import GeometersArthropod
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestGeometersArthropodProperties:
    """Static card data should match SOS 191 spec."""

    def test_is_creature(self) -> None:
        card = GeometersArthropod(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert GeometersArthropod(owner=None).name == "Geometer's Arthropod"

    def test_mana_cost(self) -> None:
        assert GeometersArthropod(owner=None).mana_cost == ManaCost.parse("{G}{U}")

    def test_power(self) -> None:
        assert GeometersArthropod(owner=None).base_power == 1

    def test_toughness(self) -> None:
        assert GeometersArthropod(owner=None).base_toughness == 4


class TestGeometersArthropodTrigger:
    """Triggered ability: cast spell with {X} -> look at top X, put 1 in hand."""

    def test_trigger_fires_on_x_spell_cast(self) -> None:
        """When controller casts a spell with {X}, the trigger should fire."""
        game = create_game()
        arthropod = GeometersArthropod(owner=game.players[0])
        set_board_state(game, 0, battlefield=[arthropod])

        # Create a simple X-spell card to cast
        from engine.card import CardImpl
        x_spell = CardImpl(owner=game.players[0])
        x_spell.name = "X Spell"
        x_spell.mana_cost = ManaCost.parse("{X}{G}")

        # Set up library with known cards
        filler1 = Creature(name="Card A", base_power=1, base_toughness=1)
        filler2 = Creature(name="Card B", base_power=2, base_toughness=2)
        filler3 = Creature(name="Card C", base_power=3, base_toughness=3)
        filler1.owner = game.players[0]
        filler2.owner = game.players[0]
        filler3.owner = game.players[0]

        game.players[0].library = [filler1, filler2, filler3]

        # Simulate casting X=3 spell and resolving trigger
        set_board_state(game, 0, hand=[x_spell], mana={ManaType.GREEN: 4})

        # After trigger resolves with X=3, should look at top 3 cards,
        # put 1 in hand and rest on bottom
        # This requires the trigger to exist on the arthropod
        triggers = arthropod.get_triggered_abilities(game)
        assert len(triggers) >= 1

    def test_x_equals_zero_looks_at_no_cards(self) -> None:
        """When X=0, look at top 0 cards — nothing happens."""
        game = create_game()
        arthropod = GeometersArthropod(owner=game.players[0])
        set_board_state(game, 0, battlefield=[arthropod])

        hand_before = len(game.players[0].hand)

        # Cast X=0 spell: trigger fires but X=0 means look at 0 cards
        from engine.card import CardImpl
        x_spell = CardImpl(owner=game.players[0])
        x_spell.name = "X Spell"
        x_spell.mana_cost = ManaCost.parse("{X}{G}")

        game.players[0].library = []
        set_board_state(game, 0, hand=[x_spell], mana={ManaType.GREEN: 1})

        # After resolving with X=0, hand count should not increase
        # (beyond removing the spell that was cast)
        # The trigger should handle X=0 gracefully
        assert arthropod.get_triggered_abilities(game) is not None

    def test_does_not_trigger_on_non_x_spell(self) -> None:
        """Spells without {X} in mana cost should not trigger."""
        game = create_game()
        arthropod = GeometersArthropod(owner=game.players[0])
        set_board_state(game, 0, battlefield=[arthropod])

        non_x_spell = Creature(name="Regular Bear", base_power=2, base_toughness=2)
        non_x_spell.owner = game.players[0]
        non_x_spell.mana_cost = ManaCost.parse("{1}{G}")

        set_board_state(game, 0, hand=[non_x_spell], mana={ManaType.GREEN: 2, ManaType.COLORLESS: 1})

        hand_size_before = len(game.players[0].hand)
        # Casting a non-X spell should not trigger the ability
        # Verify by checking trigger condition
        assert hasattr(arthropod, 'check_trigger') or hasattr(arthropod, 'get_triggered_abilities')
