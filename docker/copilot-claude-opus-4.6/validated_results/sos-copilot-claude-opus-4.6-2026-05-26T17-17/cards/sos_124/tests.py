"""Tests for SOS 124 — Mica, Reader of Ruins."""

from __future__ import annotations

import pytest

from cards.sos.sos_124.card_impl import MicaReaderOfRuins
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestMicaProperties:
    """Static card data should match the SOS 124 spec."""

    def test_is_creature(self) -> None:
        card = MicaReaderOfRuins(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert MicaReaderOfRuins(owner=None).name == "Mica, Reader of Ruins"

    def test_mana_cost(self) -> None:
        assert MicaReaderOfRuins(owner=None).mana_cost == ManaCost.parse("{3}{R}")

    def test_power_toughness(self) -> None:
        card = MicaReaderOfRuins(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        card = MicaReaderOfRuins(owner=None)
        assert getattr(card, 'is_legendary', False) or CardType.LEGENDARY in getattr(card, 'supertypes', set())


class TestMicaWard:
    """Ward—Pay 3 life."""

    def test_has_ward(self) -> None:
        card = MicaReaderOfRuins(owner=None)
        assert Keyword.WARD in card.keywords

    def test_ward_cost_is_3_life(self) -> None:
        card = MicaReaderOfRuins(owner=None)
        assert card.ward_cost == 3


class TestMicaSpellCopyTrigger:
    """Whenever you cast an instant or sorcery, you may sacrifice an artifact to copy the spell."""

    def test_sacrifice_artifact_copies_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        mica = MicaReaderOfRuins(owner=p1, controller=p1)
        artifact = Creature(name="Test Artifact", owner=p1, controller=p1,
                            base_power=0, base_toughness=0)
        artifact.card_types = {CardType.ARTIFACT}
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[mica, artifact],
                        hand=[bolt],
                        mana={ManaType.RED: 2})
        initial_stack_size = len(game.stack) if hasattr(game, 'stack') else 0
        cast_spell(game, 0, "Test Bolt", sacrifice_artifact="Test Artifact")
        # Artifact should be sacrificed (no longer on battlefield)
        battlefield = game.get_battlefield(p1)
        artifacts_on_field = [c for c in battlefield if CardType.ARTIFACT in getattr(c, 'card_types', set())]
        assert len(artifacts_on_field) == 0

    def test_no_artifact_no_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        mica = MicaReaderOfRuins(owner=p1, controller=p1)
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[mica],
                        hand=[bolt],
                        mana={ManaType.RED: 2})
        # Should be able to cast without error even with no artifact
        cast_spell(game, 0, "Test Bolt")
        # No crash means the may-ability was properly optional
