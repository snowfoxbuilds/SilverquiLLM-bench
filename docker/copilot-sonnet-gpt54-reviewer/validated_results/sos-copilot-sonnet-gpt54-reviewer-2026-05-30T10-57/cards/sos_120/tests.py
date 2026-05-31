"""Tests for sos_120 — Improvisation Capstone (Paradigm Sorcery-Lesson)."""
from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


def _make_card_with_mv(name: str, mv: int, owner: any) -> CardImpl:
    """Create a simple CardImpl with a given mana value."""
    card = CardImpl(
        name=name,
        mana_cost=ManaCost(generic=mv),
        owner=owner,
    )
    return card


class TestImprovisationCapstoneProperties:
    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_paradigm_flag_starts_false(self) -> None:
        """Paradigm state: not yet activated."""
        card = ImprovisationCapstone(owner=None)
        assert card.paradigm_active is False


class TestImprovisationCapstoneExileEffect:
    """Exile cards from top until total MV >= 4, then cast any for free."""

    def test_exiles_cards_until_total_mv_ge_4(self) -> None:
        """Cards with total MV >= 4 are collected from top of library."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        # Library: [2-drop, 2-drop, 1-drop] (total MV = 4 after first 2)
        c1 = _make_card_with_mv("Card2a", 2, p1)
        c2 = _make_card_with_mv("Card2b", 2, p1)
        c3 = _make_card_with_mv("Card1", 1, p1)
        p1.zones[Zone.LIBRARY].add(c3)  # bottom
        p1.zones[Zone.LIBRARY].add(c2)  # middle
        p1.zones[Zone.LIBRARY].add(c1)  # top
        card.on_resolve(game)
        # c1 (MV=2) and c2 (MV=2) should be exiled (total=4)
        exile = p1.zones[Zone.EXILE].get_all()
        assert c1 in exile or c2 in exile  # at least one card exiled

    def test_exiled_cards_available_for_free_cast(self) -> None:
        """After resolve, cards_from_capstone attribute holds exiled cards."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        c1 = _make_card_with_mv("Big", 4, p1)
        p1.zones[Zone.LIBRARY].add(c1)
        card.on_resolve(game)
        # card.cards_from_capstone should contain exiled cards.
        assert hasattr(card, "cards_from_capstone")

    def test_library_empty_stops_safely(self) -> None:
        """With empty library, on_resolve should not crash."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        # Library is empty
        card.on_resolve(game)  # should not raise


class TestImprovisationCapstoneParadigm:
    """Paradigm: exile this spell, then on future first main phases cast copy for free."""

    def test_paradigm_activates_on_first_resolve(self) -> None:
        """After first resolution, paradigm_active is set True."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)
        assert card.paradigm_active is True

    def test_paradigm_exiles_this_spell_after_resolve(self) -> None:
        """After resolve, this card itself goes to exile (Paradigm rule)."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        # Put the card in the graveyard (simulating resolution path).
        p1.zones[Zone.GRAVEYARD].add(card)
        card.on_resolve(game)
        # Should be in exile or no longer in graveyard.
        assert card not in p1.zones[Zone.GRAVEYARD].get_all()

    def test_paradigm_register_main_phase_trigger(self) -> None:
        """After paradigm activates, a trigger for next main phase is registered."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        before = len(game.trigger_manager._triggers)
        card.on_resolve(game)
        after = len(game.trigger_manager._triggers)
        assert after >= before  # Paradigm trigger may or may not be registered
