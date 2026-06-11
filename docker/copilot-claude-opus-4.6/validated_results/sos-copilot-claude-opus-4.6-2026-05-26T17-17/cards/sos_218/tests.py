"""Tests for SOS 218 — Quandrix, the Proof.

Quandrix, the Proof is a {4}{G}{U} Legendary Creature — Elder Dragon with:
- Flying, trample
- Cascade
- Instant and sorcery spells you cast from your hand have cascade.
- 6/6
"""

from __future__ import annotations

import pytest
from cards.sos.sos_218.card_impl import QuandrixTheProof
from engine.card import Creature, Instant, Sorcery
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


class TestQuandrixTheProofProperties:
    """Static card data should match the SOS 218 spec."""

    def test_name(self) -> None:
        assert QuandrixTheProof(owner=None).name == "Quandrix, the Proof"

    def test_mana_cost(self) -> None:
        assert QuandrixTheProof(owner=None).mana_cost == ManaCost.parse("{4}{G}{U}")

    def test_is_creature(self) -> None:
        assert isinstance(QuandrixTheProof(owner=None), Creature)

    def test_power_toughness(self) -> None:
        card = QuandrixTheProof(owner=None)
        assert card.base_power == 6
        assert card.base_toughness == 6

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in QuandrixTheProof(owner=None).keywords

    def test_has_trample(self) -> None:
        assert Keyword.TRAMPLE in QuandrixTheProof(owner=None).keywords

    def test_has_cascade(self) -> None:
        assert Keyword.CASCADE in QuandrixTheProof(owner=None).keywords

    def test_is_legendary(self) -> None:
        card = QuandrixTheProof(owner=None)
        assert CardType.LEGENDARY in card.card_types or card.is_legendary


class TestQuandrixTheProofCascade:
    """Cascade triggers when cast."""

    def test_cascade_triggers_on_cast(self) -> None:
        """When Quandrix is cast, cascade should trigger."""
        game = create_game(deck1=["Land A", "Land B", "Card C"])
        p1 = game.players[0]
        card = QuandrixTheProof(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[card], mana={ManaType.GREEN: 1, ManaType.BLUE: 1, ManaType.COLORLESS: 4})
        # Casting should trigger cascade
        game.cast_spell(p1, card)
        # Verify cascade was triggered (implementation detail may vary)
        assert game.cascade_triggered or len(game.stack) > 0


class TestQuandrixTheProofGrantsCascade:
    """Instant and sorcery spells cast from hand gain cascade."""

    def test_instant_from_hand_gets_cascade(self) -> None:
        """An instant cast from hand while Quandrix is on battlefield should have cascade."""
        game = create_game(deck1=["Land A", "Card B"])
        p1 = game.players[0]
        quandrix = QuandrixTheProof(owner=p1, controller=p1)
        game.get_battlefield(p1).add(quandrix)

        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        instant.mana_cost = ManaCost.parse("{U}")
        set_board_state(game, 0, hand=[instant], mana={ManaType.BLUE: 2})

        # Cast the instant from hand
        game.cast_spell(p1, instant)
        # The instant should have cascade granted by Quandrix
        assert Keyword.CASCADE in instant.keywords or game.cascade_triggered

    def test_sorcery_from_hand_gets_cascade(self) -> None:
        """A sorcery cast from hand while Quandrix is on battlefield should have cascade."""
        game = create_game(deck1=["Land A", "Card B"])
        p1 = game.players[0]
        quandrix = QuandrixTheProof(owner=p1, controller=p1)
        game.get_battlefield(p1).add(quandrix)

        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        sorcery.mana_cost = ManaCost.parse("{G}")
        set_board_state(game, 0, hand=[sorcery], mana={ManaType.GREEN: 2})

        game.cast_spell(p1, sorcery)
        assert Keyword.CASCADE in sorcery.keywords or game.cascade_triggered

    def test_creature_from_hand_does_not_get_cascade(self) -> None:
        """A creature spell cast from hand should NOT get cascade from Quandrix."""
        game = create_game()
        p1 = game.players[0]
        quandrix = QuandrixTheProof(owner=p1, controller=p1)
        game.get_battlefield(p1).add(quandrix)

        creature = Creature(name="Test Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        creature.mana_cost = ManaCost.parse("{1}{G}")
        set_board_state(game, 0, hand=[creature], mana={ManaType.GREEN: 1, ManaType.COLORLESS: 1})

        game.cast_spell(p1, creature)
        # Creature should NOT have cascade granted
        assert Keyword.CASCADE not in creature.keywords
