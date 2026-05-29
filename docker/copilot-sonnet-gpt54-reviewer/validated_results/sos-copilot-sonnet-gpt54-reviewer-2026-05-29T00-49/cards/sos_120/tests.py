"""Tests for sos_120 — Improvisation Capstone.

Covers:
- Static card properties (name, mana cost, type, Lesson subtype)
- Main effect: exile cards from top of library until total CMC >= 4
- Exiling stops when accumulated CMC >= 4
- All exiled cards are available for free casting
- Empty library does not crash
- Single card with CMC >= 4 satisfies the condition immediately
- Paradigm: after resolution, the spell is exiled (not graveyard)
- Paradigm: has_resolved_once state tracking
- Paradigm: triggers are registered for main phase free-copy cast
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Sorcery, Instant, CardImpl
from engine.types import (
    CardType,
    ManaCost,
    ManaType,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(game: Any, player: Any, name: str, cmc: int, card_class: type = Sorcery) -> CardImpl:
    """Create a card with the given CMC owned by player."""
    if cmc == 0:
        mana_cost_obj = ManaCost()
    else:
        mana_cost_obj = ManaCost.parse(f"{{{cmc}}}")
    card = card_class(
        name=name,
        mana_cost=mana_cost_obj,
        owner=player,
        controller=player,
    )
    return card


def _put_in_library(game: Any, player: Any, cards: list[Any]) -> None:
    """Put cards into the player's library zone (bottom to top order)."""
    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card, position="bottom")


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneProperties:
    """Static card data should match the sos_120 spec."""

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_mana_cost_cmc_is_seven(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7


# ---------------------------------------------------------------------------
# Library exile effect — stops at total CMC >= 4
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneExileEffect:
    """on_resolve exiles cards from library top until total CMC >= 4."""

    def test_single_card_cmc4_exiled_and_stops(self) -> None:
        """A single card with CMC 4 should be exiled and stop the loop."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        card_a = _make_card(game, p1, "BigSpell", cmc=4)
        card_b = _make_card(game, p1, "LeftoverSpell", cmc=2)
        _put_in_library(game, p1, [card_b, card_a])  # card_a on top

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        library = game.get_library(p1)
        assert exile.contains(card_a), "Card with CMC 4 should be exiled"
        assert library.contains(card_b), "Card after threshold should remain in library"

    def test_multiple_cards_exiled_until_cmc_reaches_4(self) -> None:
        """Cards with CMC 1, 1, 2 should all be exiled (total = 4)."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        card1 = _make_card(game, p1, "Card1", cmc=1)
        card2 = _make_card(game, p1, "Card2", cmc=1)
        card3 = _make_card(game, p1, "Card3", cmc=2)
        card4 = _make_card(game, p1, "Card4", cmc=3)  # should stay in library
        # Put on library: card1 is top, card4 is bottom
        _put_in_library(game, p1, [card4, card3, card2, card1])

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        library = game.get_library(p1)
        assert exile.contains(card1), "Card1 (CMC 1) should be exiled"
        assert exile.contains(card2), "Card2 (CMC 1) should be exiled"
        assert exile.contains(card3), "Card3 (CMC 2) should be exiled (total=4)"
        assert library.contains(card4), "Card4 should remain in library (threshold met)"

    def test_does_not_exile_more_than_needed(self) -> None:
        """Exiling stops as soon as total CMC >= 4; extra cards stay in library."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        card_a = _make_card(game, p1, "CardA", cmc=5)  # immediately satisfies
        card_b = _make_card(game, p1, "CardB", cmc=3)  # should stay
        _put_in_library(game, p1, [card_b, card_a])  # card_a on top

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        library = game.get_library(p1)
        assert exile.contains(card_a)
        assert not exile.contains(card_b), "CardB should NOT be exiled — threshold met after CardA"

    def test_empty_library_does_not_raise(self) -> None:
        """If the library is empty, on_resolve should complete without error."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        _put_in_library(game, p1, [])  # ensure empty

        try:
            spell.on_resolve(game)
        except Exception as exc:
            pytest.fail(f"on_resolve raised unexpectedly on empty library: {exc}")

    def test_library_with_only_cmc0_cards_exiles_all(self) -> None:
        """If all library cards have CMC 0, the entire library is exiled (never satisfies)."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        zero_cards = [_make_card(game, p1, f"Zero{i}", cmc=0) for i in range(3)]
        _put_in_library(game, p1, list(reversed(zero_cards)))

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        for card in zero_cards:
            assert exile.contains(card), f"{card.name} with CMC 0 should be exiled"

    def test_exiled_cards_removed_from_library(self) -> None:
        """After exiling, cards should no longer be in the library."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        card_a = _make_card(game, p1, "Target", cmc=4)
        _put_in_library(game, p1, [card_a])

        spell.on_resolve(game)

        library = game.get_library(p1)
        assert not library.contains(card_a), "Exiled card must be removed from library"


# ---------------------------------------------------------------------------
# Free casting of exiled cards
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneFreeCast:
    """Cards exiled by on_resolve can be cast for free."""

    def test_exiled_cards_marked_for_free_cast(self) -> None:
        """After on_resolve, cards exiled by the effect should be castable for free."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        card_a = _make_card(game, p1, "FreeCard", cmc=4)
        _put_in_library(game, p1, [card_a])

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(card_a), "Card should be in exile after resolve"

        # The card should be accessible for free casting — marked or tracked
        # via the spell object or game state. Check at least one of these:
        # - The spell has a record of exiled cards (e.g., spell.exiled_cards)
        # - Or the card has a flag indicating free-cast eligibility
        has_exiled_record = (
            hasattr(spell, "exiled_cards") and card_a in spell.exiled_cards
        ) or (
            hasattr(card_a, "cast_for_free") and card_a.cast_for_free
        ) or (
            hasattr(card_a, "exiled_by_capstone") and card_a.exiled_by_capstone
        )
        assert has_exiled_record, (
            "Exiled card should be tracked for free casting by the spell or card attribute"
        )

    def test_on_resolve_does_not_spend_player_mana(self) -> None:
        """Casting exiled cards for free means the player doesn't spend mana."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        card_a = _make_card(game, p1, "ExpensiveCard", cmc=5)
        _put_in_library(game, p1, [card_a])
        # Player has no mana — the free cast should work anyway
        p1.mana_pool.empty()

        # on_resolve should not raise even without mana
        try:
            spell.on_resolve(game)
        except Exception as exc:
            pytest.fail(f"on_resolve raised without player mana: {exc}")


# ---------------------------------------------------------------------------
# Paradigm: exile this spell after resolution
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmExile:
    """Paradigm mechanic: spell is exiled after resolution, not sent to graveyard."""

    def test_paradigm_exiles_spell_after_resolution(self) -> None:
        """After on_resolve, the spell should be in exile, not the graveyard."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        # Simulate the spell being on the stack then resolved
        stack_zone = p1.zones[Zone.STACK]
        stack_zone.add(spell)

        _put_in_library(game, p1, [])  # empty library — focus on exile mechanic

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(spell), "Spell must NOT go to graveyard (Paradigm)"
        assert exile.contains(spell), "Spell must go to exile (Paradigm)"

    def test_paradigm_exile_registers_replacement_effect(self) -> None:
        """register_replacement_effects should register a graveyard→exile replacement."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        before = len(game.replacement_manager._effects)
        spell.register_replacement_effects(game)
        after = len(game.replacement_manager._effects)
        assert after > before, "Paradigm should register a replacement effect"


# ---------------------------------------------------------------------------
# Paradigm: has_resolved_once state tracking
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmState:
    """Paradigm state: card tracks whether it has resolved once."""

    def test_has_resolved_once_false_initially(self) -> None:
        """A freshly created card should not have resolved yet."""
        card = ImprovisationCapstone(owner=None)
        resolved = getattr(card, "has_resolved_once", False)
        assert resolved is False, "has_resolved_once should be False before first resolution"

    def test_has_resolved_once_set_after_resolve(self) -> None:
        """After on_resolve completes, has_resolved_once should be True."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        stack_zone = p1.zones[Zone.STACK]
        stack_zone.add(spell)
        _put_in_library(game, p1, [])

        spell.on_resolve(game)

        assert getattr(spell, "has_resolved_once", False) is True, (
            "has_resolved_once should be True after first resolution"
        )

    def test_paradigm_trigger_registered_for_main_phase(self) -> None:
        """register_triggers should register at least one trigger for the Paradigm."""
        game = create_game()
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        before = len(game.trigger_manager.get_triggers())
        spell.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before, "Paradigm should register at least one trigger"
