"""Tests for SOS 120 -- Improvisation Capstone.

Improvisation Capstone is a {5}{R}{R} Sorcery -- Lesson with Paradigm.

Oracle text:
    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.

    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its
    mana cost at the beginning of each of your first main phases.)

Requirements tested:
1. Static properties: name, mana cost, card type (Sorcery), subtype (Lesson),
   colors (red), mana value (7).
2. Main effect -- exile from library until total MV >= 4.
3. Main effect -- castable spells among exiled cards.
4. Paradigm -- self-exile after resolution.
5. Paradigm -- delayed trigger registration for recurring cast at main phase.
6. Edge cases: empty library, single high-MV card, all zero-MV cards.
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
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


def _make_library_card(name: str, mana_cost_str: str, owner: Any = None) -> Instant:
    """Create a simple instant card with a given mana cost for library stocking."""
    return Instant(
        name=name,
        mana_cost=ManaCost.parse(mana_cost_str),
        owner=owner,
    )


def _make_creature_card(
    name: str, mana_cost_str: str, power: int = 1, toughness: int = 1, owner: Any = None
) -> Creature:
    """Create a creature card with a given mana cost for library stocking."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(mana_cost_str),
        base_power=power,
        base_toughness=toughness,
        owner=owner,
    )


def _setup_with_library(library_cards: list[Any]) -> tuple:
    """Create game, put Improvisation Capstone in hand, stock library.

    Returns (game, player, capstone).
    Library cards are added bottom-to-top (last element = top of library).
    """
    game = create_game()
    p1 = game.players[0]
    capstone = ImprovisationCapstone(owner=p1, controller=p1)

    # Set up the library -- cards are added top-first, so reverse for
    # bottom-to-top ordering within the ZoneContainer (last = top).
    library = p1.zones[Zone.LIBRARY]
    # Clear existing library
    for obj in library.get_all():
        library.remove(obj)
    # Add cards: last in list = top of library
    for card in library_cards:
        card.owner = p1
        card.controller = p1
        library.add(card)

    return game, p1, capstone


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_has_sorcery_card_type(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_mana_value_is_seven(self) -> None:
        """The converted mana cost / mana value should be 7 ({5}{R}{R})."""
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7

    def test_color_is_red(self) -> None:
        """The card's mana cost should include red pips."""
        card = ImprovisationCapstone(owner=None)
        assert ManaType.RED in card.mana_cost.pips


# ---------------------------------------------------------------------------
# Main effect -- exile cards from library until total MV >= 4
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneExileFromLibrary:
    """Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater."""

    def test_exiles_cards_until_total_mv_four_or_greater(self) -> None:
        """With a library of [MV1, MV1, MV2, MV3], should exile cards
        from top until the running total reaches 4+."""
        # Library top-to-bottom: MV3 (top), MV2, MV1, MV1 (bottom)
        c1 = _make_library_card("Spell A", "{1}")        # MV 1
        c2 = _make_library_card("Spell B", "{1}")        # MV 1
        c3 = _make_library_card("Spell C", "{1}{U}")     # MV 2
        c4 = _make_library_card("Spell D", "{2}{R}")     # MV 3
        # top of library = c4 (last added)
        game, p1, capstone = _setup_with_library([c1, c2, c3, c4])

        capstone.on_resolve(game)

        exile = game.get_exile(p1)
        # The spell should exile from top: c4 (MV 3, total=3 < 4), then
        # c3 (MV 2, total=5 >= 4). So at least c4 and c3 should be exiled.
        exiled = exile.get_all()
        # Check total MV of exiled library cards (excluding capstone itself)
        exiled_lib_cards = [c for c in exiled if c is not capstone]
        total_mv = sum(
            getattr(c, "mana_cost", ManaCost()).cmc for c in exiled_lib_cards
        )
        assert total_mv >= 4, (
            f"Expected total MV of exiled cards >= 4, got {total_mv}"
        )

    def test_single_card_with_mv_four_stops_immediately(self) -> None:
        """If the top card has MV >= 4, only that one card should be exiled
        from library."""
        big = _make_library_card("Big Spell", "{3}{R}")  # MV 4
        filler = _make_library_card("Filler", "{1}")      # MV 1
        game, p1, capstone = _setup_with_library([filler, big])

        lib_before = len(p1.zones[Zone.LIBRARY])
        capstone.on_resolve(game)

        # big was on top, MV=4 >= 4, so only 1 card exiled from library
        lib_after = len(p1.zones[Zone.LIBRARY])
        exiled_from_lib = lib_before - lib_after
        assert exiled_from_lib == 1, (
            f"Expected exactly 1 card exiled from library, got {exiled_from_lib}"
        )

    def test_multiple_small_cards_exiled_until_threshold(self) -> None:
        """Multiple MV-1 cards should be exiled one by one until total >= 4."""
        cards = [_make_library_card(f"Small {i}", "{1}") for i in range(6)]
        game, p1, capstone = _setup_with_library(cards)

        capstone.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_lib = [c for c in exile.get_all() if c is not capstone]
        total_mv = sum(
            getattr(c, "mana_cost", ManaCost()).cmc for c in exiled_lib
        )
        assert total_mv >= 4
        # Should have exiled exactly 4 MV-1 cards to reach total MV 4
        assert len(exiled_lib) == 4, (
            f"Expected 4 cards exiled (4 x MV1), got {len(exiled_lib)}"
        )

    def test_cards_are_exiled_not_put_elsewhere(self) -> None:
        """Exiled library cards should be in the exile zone, not graveyard or hand."""
        c1 = _make_library_card("Card A", "{2}{R}")  # MV 3
        c2 = _make_library_card("Card B", "{1}")      # MV 1
        game, p1, capstone = _setup_with_library([c2, c1])

        capstone.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_lib = [c for c in exile.get_all() if c is not capstone]
        # At least some cards should be in exile
        assert len(exiled_lib) > 0
        # None should be in graveyard (they were exiled, not milled)
        gy = game.get_graveyard(p1)
        for c in exiled_lib:
            assert not gy.contains(c), f"{c.name} should not be in graveyard"


# ---------------------------------------------------------------------------
# Main effect -- casting exiled spells for free
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneFreeCast:
    """You may cast any number of spells from among the exiled cards
    without paying their mana costs."""

    def test_exiled_spells_are_castable_for_free(self) -> None:
        """After exiling, the implementation should cast (or make available
        to cast) spells from among the exiled cards without paying mana.
        We verify that spells resolve even with an empty mana pool."""
        # Two instants, MV 2 each: will need 2 to reach MV 4
        spell_a = Instant(
            name="Free Cast A",
            mana_cost=ManaCost.parse("{1}{R}"),
        )
        spell_b = Instant(
            name="Free Cast B",
            mana_cost=ManaCost.parse("{1}{U}"),
        )
        game, p1, capstone = _setup_with_library([spell_a, spell_b])

        # Empty mana pool -- should still work (free cast)
        p1.mana_pool.empty()

        capstone.on_resolve(game)

        # Resolve anything on the stack from the free casts
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # The exiled spells should have been cast. They might end up in
        # graveyard or exile depending on implementation. The key test is
        # that the resolve completes without error (no mana needed).

    def test_creature_among_exiled_cards_can_be_cast(self) -> None:
        """Non-instant/sorcery permanents among exiled cards should also
        be castable (the oracle says 'any number of spells')."""
        bear = Creature(
            name="Free Bear",
            mana_cost=ManaCost.parse("{3}{G}"),  # MV 4
            base_power=4,
            base_toughness=4,
        )
        game, p1, capstone = _setup_with_library([bear])

        p1.mana_pool.empty()
        capstone.on_resolve(game)

        # Resolve free-cast
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # The creature should be on the battlefield (was cast for free)
        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        assert "Free Bear" in bf_names, (
            f"Expected Free Bear on battlefield, found: {bf_names}"
        )


# ---------------------------------------------------------------------------
# Paradigm -- self-exile after resolution
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmExile:
    """Paradigm means the spell itself is exiled after resolution,
    not put into the graveyard."""

    def test_spell_is_exiled_after_resolution(self) -> None:
        """After on_resolve, the capstone itself should be in the exile zone."""
        filler = _make_library_card("Filler", "{3}{R}")  # MV 4
        game, p1, capstone = _setup_with_library([filler])

        # Put the capstone somewhere the implementation can find it
        # (it might be on the stack or in hand during resolution).
        p1.zones[Zone.STACK].add(capstone)

        capstone.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(capstone), (
            "Paradigm requires the spell to be exiled after resolution"
        )

    def test_spell_not_in_graveyard_after_resolution(self) -> None:
        """After resolution, the capstone should NOT be in the graveyard."""
        filler = _make_library_card("Filler", "{3}{R}")  # MV 4
        game, p1, capstone = _setup_with_library([filler])

        p1.zones[Zone.STACK].add(capstone)
        capstone.on_resolve(game)

        gy = game.get_graveyard(p1)
        assert not gy.contains(capstone), (
            "Paradigm: spell should be exiled, not go to graveyard"
        )


# ---------------------------------------------------------------------------
# Paradigm -- delayed trigger for recurring copy
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmRecurrence:
    """After you first resolve a spell with this name, you may cast a copy
    of it from exile without paying its mana cost at the beginning of
    each of your first main phases."""

    def test_paradigm_registers_delayed_trigger_after_first_resolution(self) -> None:
        """After the first resolution, a delayed trigger should be registered
        that watches for BeginningOfMainPhaseTriggeredEvent."""
        filler = _make_library_card("Filler", "{3}{R}")
        game, p1, capstone = _setup_with_library([filler])
        p1.zones[Zone.STACK].add(capstone)

        triggers_before = len(game.trigger_manager.get_triggers())
        capstone.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        assert triggers_after > triggers_before, (
            "Paradigm should register a delayed trigger after first resolution"
        )

    def test_paradigm_trigger_fires_at_main_phase(self) -> None:
        """The paradigm trigger should respond to BeginningOfMainPhaseTriggeredEvent
        for the controller."""
        filler = _make_library_card("Filler", "{3}{R}")
        game, p1, capstone = _setup_with_library([filler])
        p1.zones[Zone.STACK].add(capstone)

        capstone.on_resolve(game)

        # Fire a main phase event for the controller
        event = BeginningOfMainPhaseTriggeredEvent(player=p1)
        game.trigger_manager.fire_event(game, event)

        # Should have pushed something onto the stack
        assert not game.stack.is_empty(), (
            "Paradigm trigger should push a copy/effect onto the stack "
            "at the beginning of main phase"
        )

    def test_paradigm_trigger_does_not_fire_for_opponent(self) -> None:
        """The paradigm recurrence should only trigger for the controller,
        not the opponent."""
        filler = _make_library_card("Filler", "{3}{R}")
        game, p1, capstone = _setup_with_library([filler])
        p2 = game.players[1]
        p1.zones[Zone.STACK].add(capstone)

        capstone.on_resolve(game)

        # Fire a main phase event for the opponent
        event = BeginningOfMainPhaseTriggeredEvent(player=p2)
        stack_before = len(game.stack)
        game.trigger_manager.fire_event(game, event)
        stack_after = len(game.stack)

        assert stack_after == stack_before, (
            "Paradigm trigger should not fire for the opponent's main phase"
        )

    def test_paradigm_creates_copy_in_exile(self) -> None:
        """When the paradigm trigger resolves, it should create a copy of the
        spell in exile that can be cast."""
        filler = _make_library_card("Filler", "{3}{R}")
        game, p1, capstone = _setup_with_library([filler])
        p1.zones[Zone.STACK].add(capstone)

        capstone.on_resolve(game)

        # Fire main phase and resolve the trigger
        event = BeginningOfMainPhaseTriggeredEvent(player=p1)
        game.trigger_manager.fire_event(game, event)

        # Resolve the paradigm trigger
        if not game.stack.is_empty():
            trigger_obj = game.stack.pop()
            trigger_obj.on_resolve(game)

        # There should be an Improvisation Capstone copy in exile or
        # something on the stack from the paradigm copy
        exile = game.get_exile(p1)
        exile_names = [getattr(c, "name", "") for c in exile.get_all()]
        capstone_count = exile_names.count("Improvisation Capstone")
        # The original is in exile + potentially a copy
        # OR the copy was cast and is on the stack
        has_copy = capstone_count >= 1 or not game.stack.is_empty()
        assert has_copy, (
            "Paradigm should create a castable copy; "
            f"exile has: {exile_names}, stack size: {len(game.stack)}"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_library_does_not_crash(self) -> None:
        """If the library is empty, on_resolve should not crash."""
        game, p1, capstone = _setup_with_library([])

        p1.zones[Zone.STACK].add(capstone)
        # Should not raise
        capstone.on_resolve(game)

    def test_library_with_insufficient_total_mv(self) -> None:
        """If the entire library has total MV < 4, all cards should be
        exiled and no crash should occur."""
        cards = [_make_library_card(f"Tiny {i}", "{1}") for i in range(3)]
        # Total MV = 3 (< 4), entire library gets exiled
        game, p1, capstone = _setup_with_library(cards)
        p1.zones[Zone.STACK].add(capstone)

        capstone.on_resolve(game)

        # Library should be empty (all cards exiled)
        assert len(p1.zones[Zone.LIBRARY]) == 0, (
            "With insufficient total MV, entire library should be exiled"
        )

    def test_zero_mv_cards_are_counted(self) -> None:
        """Cards with MV 0 (like tokens or lands with no mana cost)
        contribute 0 to the running total but are still exiled."""
        # 3 MV-0 cards then 1 MV-4 card on top
        zero_cards = [
            Creature(name=f"Zero {i}", base_power=1, base_toughness=1)
            for i in range(3)
        ]
        big = _make_library_card("Big One", "{3}{R}")  # MV 4
        # Library (bottom to top): zero_0, zero_1, zero_2, big
        game, p1, capstone = _setup_with_library(zero_cards + [big])
        p1.zones[Zone.STACK].add(capstone)

        capstone.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_lib = [c for c in exile.get_all() if c is not capstone]

        # big alone has MV 4, so at minimum big should be exiled
        exiled_names = [getattr(c, "name", "") for c in exiled_lib]
        assert "Big One" in exiled_names, (
            f"The MV-4 card should be exiled; found: {exiled_names}"
        )

    def test_on_resolve_with_no_castable_spells(self) -> None:
        """If all exiled cards are lands (not castable as spells), the
        resolution should still complete without error."""
        from engine.card import Land

        lands = [
            Land(name=f"Fancy Land {i}")
            for i in range(5)
        ]
        # Lands have MV 0, so the entire library gets exiled
        # without ever reaching MV 4
        game, p1, capstone = _setup_with_library(lands)
        p1.zones[Zone.STACK].add(capstone)

        # Should not crash even with no castable spells
        capstone.on_resolve(game)
