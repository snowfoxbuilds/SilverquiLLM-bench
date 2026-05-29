"""Tests for Improvisation Capstone (SOS 120).

Card spec:
  Name: Improvisation Capstone
  Mana cost: {5}{R}{R}
  Type: Sorcery — Lesson
  Oracle: Exile cards from the top of your library until you exile cards
          with total mana value 4 or greater. You may cast any number of
          spells from among them without paying their mana costs.
          Paradigm (Then exile this spell. After you first resolve a spell
          with this name, you may cast a copy of it from exile without
          paying its mana cost at the beginning of each of your first
          main phases.)
"""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Sorcery, Instant, Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(name: str, mana_cost_str: str, card_type: type = Sorcery) -> CardImpl:
    """Create a simple card with a given name and mana cost."""
    return card_type(name=name, mana_cost=ManaCost.parse(mana_cost_str))


# ---------------------------------------------------------------------------
# Static properties
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneProperties:
    """Static card data must match the spec."""

    def test_is_sorcery_instance(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        expected = ManaCost.parse("{5}{R}{R}")
        assert card.mana_cost == expected

    def test_card_type_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_mana_cost_cmc(self) -> None:
        """Total mana cost should be 7 (5 generic + 2 red)."""
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7


# ---------------------------------------------------------------------------
# Exile mechanic — exiling cards until total MV >= 4
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneExileMechanic:
    """on_resolve must exile cards from the top of the library until total MV >= 4."""

    def test_single_card_mv4_exiled(self) -> None:
        """A single card with MV 4 satisfies the condition; only that card is exiled."""
        game = create_game()
        p1 = game.players[0]

        # Build library: one card with MV exactly 4, then another card
        card_mv4 = _make_card("Big Spell", "{2}{R}{R}")   # MV = 4
        extra_card = _make_card("Small Spell", "{1}")      # MV = 1

        # Place library in order: card_mv4 is on top (first exiled)
        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)
        # Add extra_card first (bottom), then card_mv4 (top)
        card_mv4.owner = p1
        card_mv4.controller = p1
        extra_card.owner = p1
        extra_card.controller = p1
        library.add(extra_card)
        library.add(card_mv4)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile_cards = game.get_exile(p1).get_all()
        exile_names = [c.name for c in exile_cards if c is not spell]
        # card_mv4 should be in exile; extra_card should still be in library
        assert "Big Spell" in exile_names, f"Expected 'Big Spell' in exile, got {exile_names}"
        # extra_card not exiled
        assert "Small Spell" not in exile_names, (
            "Should not have exiled 'Small Spell' — MV threshold already met"
        )

    def test_multiple_low_mv_cards_exiled_until_threshold(self) -> None:
        """If each card has MV 1, it should exile 4 cards to reach total MV >= 4."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        cards = []
        for i in range(6):
            c = _make_card(f"One-Drop {i}", "{R}")   # MV = 1 each
            c.owner = p1
            c.controller = p1
            cards.append(c)

        # Add bottom to top: cards[0] at bottom, cards[5] at top
        for c in cards:
            library.add(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        exiled = [c for c in exile.get_all() if c is not spell]
        # Should have exiled exactly 4 cards (4 * MV1 = total MV 4)
        assert len(exiled) == 4, f"Expected 4 exiled cards, got {len(exiled)}: {[c.name for c in exiled]}"

    def test_exiled_cards_land_in_exile_zone(self) -> None:
        """All library cards exiled by the effect must appear in the exile zone."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        # One card with MV 5 — single card satisfies MV >= 4
        big = _make_card("Huge Spell", "{3}{R}{R}")  # MV = 5
        big.owner = p1
        big.controller = p1
        library.add(big)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile_cards = game.get_exile(p1).get_all()
        assert any(c.name == "Huge Spell" for c in exile_cards), (
            "Exiled library card must appear in exile zone"
        )

    def test_exiled_cards_removed_from_library(self) -> None:
        """Cards exiled from the library must no longer be in the library."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        target = _make_card("Spell", "{2}{U}{U}")  # MV = 4
        target.owner = p1
        target.controller = p1
        library.add(target)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        lib_cards = library.get_all()
        assert not any(c.name == "Spell" for c in lib_cards), (
            "Exiled card should no longer be in the library"
        )

    def test_empty_library_does_not_crash(self) -> None:
        """If the library is empty, on_resolve should not raise an exception."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Should not raise
        spell.on_resolve(game)

    def test_two_cards_with_combined_mv4_both_exiled(self) -> None:
        """Two MV-2 cards sum to 4 — both should be exiled, not just one."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        c1 = _make_card("Card A", "{R}{R}")   # MV = 2
        c2 = _make_card("Card B", "{G}{G}")   # MV = 2
        c3 = _make_card("Card C", "{W}")      # MV = 1, should NOT be exiled
        c1.owner = p1; c1.controller = p1
        c2.owner = p1; c2.controller = p1
        c3.owner = p1; c3.controller = p1

        # Library top-to-bottom: c1 (top), c2, c3 (bottom)
        library.add(c3)
        library.add(c2)
        library.add(c1)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exiled = [c for c in game.get_exile(p1).get_all() if c is not spell]
        exiled_names = [c.name for c in exiled]
        assert "Card A" in exiled_names, "Card A (MV 2) should be exiled"
        assert "Card B" in exiled_names, "Card B (MV 2) should be exiled (total reaches 4)"
        assert "Card C" not in exiled_names, "Card C should NOT be exiled (threshold already met)"

    def test_mv3_plus_mv1_stops_at_mv4(self) -> None:
        """MV 3 + MV 1 = 4 total; exiling should stop after the MV-1 card."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        c1 = _make_card("Three Drop", "{1}{U}{U}")   # MV = 3
        c2 = _make_card("One Drop", "{R}")             # MV = 1  (running total = 4)
        c3 = _make_card("Extra Card", "{G}{G}")        # MV = 2, should NOT be exiled
        c1.owner = p1; c1.controller = p1
        c2.owner = p1; c2.controller = p1
        c3.owner = p1; c3.controller = p1

        library.add(c3)
        library.add(c2)
        library.add(c1)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exiled = [c for c in game.get_exile(p1).get_all() if c is not spell]
        exiled_names = [c.name for c in exiled]
        assert "Three Drop" in exiled_names
        assert "One Drop" in exiled_names
        assert "Extra Card" not in exiled_names, "Extra Card should not be exiled after threshold hit"


# ---------------------------------------------------------------------------
# Free casting from exiled cards
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneFreeCasting:
    """After resolution, the player may cast the exiled library cards for free."""

    def test_exiled_cards_marked_as_free_cast_eligible(self) -> None:
        """
        After on_resolve, exiled cards should be available to cast for free.
        The implementation must store the set of free-castable cards somewhere
        accessible (e.g. a 'free_cast_from_exile' attribute on the spell or player).
        """
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        target = _make_card("Castable Spell", "{2}{R}{R}")  # MV = 4
        target.owner = p1
        target.controller = p1
        library.add(target)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # The exiled card should be in exile zone (testable directly)
        exile = game.get_exile(p1)
        assert any(c.name == "Castable Spell" for c in exile.get_all()), (
            "Exiled library card must be in exile zone for free casting"
        )

        # At minimum, the spell must track which cards were exiled for free casting
        exiled_for_cast = getattr(spell, "exiled_for_free_cast", None)
        assert exiled_for_cast is not None, (
            "ImprovisationCapstone must track 'exiled_for_free_cast' cards"
        )
        assert target in exiled_for_cast, (
            "The exiled library card must be in exiled_for_free_cast"
        )


# ---------------------------------------------------------------------------
# Paradigm — exile this spell on resolution
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigm:
    """Paradigm: After resolution, the spell itself goes to exile (not graveyard)."""

    def test_spell_goes_to_exile_after_resolution(self) -> None:
        """
        The spell must be in exile after on_resolve, not in graveyard.
        Normal sorcery resolution puts the card in graveyard; Paradigm overrides this.
        The implementation signals 'go to exile' via an attribute checked by the
        casting engine.
        """
        game = create_game()
        p1 = game.players[0]

        # Empty library so on_resolve doesn't fail on missing library cards
        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Check that the spell signalled it should go to exile
        # (implementations typically set go_to_exile=True or similar)
        assert getattr(spell, "go_to_exile", False) is True, (
            "Paradigm requires the spell to signal it should be exiled, not sent to graveyard. "
            "Expected 'go_to_exile' attribute to be True after on_resolve."
        )

    def test_spell_not_in_graveyard_after_resolution(self) -> None:
        """After resolution, the Paradigm spell should NOT end up in graveyard."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Manually place in hand, then cast to trigger full resolution path
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")

        graveyard_cards = game.get_graveyard(p1).get_all()
        assert not any(
            c.name == "Improvisation Capstone" for c in graveyard_cards
        ), "Paradigm spell must NOT appear in graveyard after resolution"

    def test_spell_in_exile_after_cast(self) -> None:
        """After casting and resolving, the Paradigm spell should be in exile."""
        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell],
                        mana={ManaType.RED: 7, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")

        exile_cards = game.get_exile(p1).get_all()
        assert any(
            c.name == "Improvisation Capstone" for c in exile_cards
        ), "Paradigm spell must appear in exile after resolution"

    def test_paradigm_trigger_registered_for_main_phase(self) -> None:
        """
        After first resolution, a trigger for BeginningOfMainPhaseTriggeredEvent
        must be registered so a copy can be offered each turn.
        """
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        initial_trigger_count = len([
            t for t in game.trigger_manager._triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ])

        spell.on_resolve(game)

        new_trigger_count = len([
            t for t in game.trigger_manager._triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ])
        assert new_trigger_count > initial_trigger_count, (
            "Paradigm must register a BeginningOfMainPhaseTriggeredEvent trigger "
            "after first resolution so a free copy can be cast each turn"
        )

    def test_paradigm_trigger_fires_at_main_phase_start(self) -> None:
        """
        After resolution, the Paradigm trigger should fire at the beginning of
        the controller's first main phase, making a free copy available.
        """
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        game = create_game()
        p1 = game.players[0]

        library = game.get_library(p1)
        for c in library.get_all():
            library.remove(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Manually fire the BeginningOfMainPhaseTriggeredEvent for p1
        # to simulate what happens at start of precombat main phase
        fired = []
        # Find the paradigm trigger and verify it responds to p1's main phase
        paradigm_triggers = [
            t for t in game.trigger_manager._triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert paradigm_triggers, "Must have a paradigm trigger registered"

        event = BeginningOfMainPhaseTriggeredEvent(active_player=p1)
        # Check at least one trigger fires for this event
        for trigger in paradigm_triggers:
            cond = trigger.condition
            if cond is None or cond(game, event):
                fired.append(trigger)

        assert fired, (
            "Paradigm trigger must match the active player's first main phase event"
        )
