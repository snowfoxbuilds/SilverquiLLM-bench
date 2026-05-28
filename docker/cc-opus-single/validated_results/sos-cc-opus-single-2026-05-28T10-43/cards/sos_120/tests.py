"""Tests for SOS 120 — Improvisation Capstone.

Improvisation Capstone is a {5}{R}{R} Sorcery — Lesson with Paradigm.

Oracle text:
  Exile cards from the top of your library until you exile cards with total
  mana value 4 or greater. You may cast any number of spells from among them
  without paying their mana costs.

  Paradigm (Then exile this spell. After you first resolve a spell with this
  name, you may cast a copy of it from exile without paying its mana cost at
  the beginning of each of your first main phases.)

Requirements tested:
- Static properties (name, mana cost, card type, subtypes)
- Exile-from-library mechanic: exile until total MV >= 4
- Free-cast from among exiled cards
- Paradigm: spell is exiled instead of going to graveyard
- Paradigm: delayed trigger on precombat main phases after first resolution
- Edge cases: empty library, all lands exiled, exact MV threshold
"""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper: create simple cards with known mana values for library stacking
# ---------------------------------------------------------------------------

def _make_creature(name: str, mana_cost_str: str, power: int = 1, toughness: int = 1) -> Creature:
    """Create a simple creature with the given mana cost."""
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(mana_cost_str),
        base_power=power,
        base_toughness=toughness,
    )


def _make_sorcery(name: str, mana_cost_str: str) -> Sorcery:
    """Create a simple sorcery with the given mana cost."""
    return Sorcery(
        name=name,
        mana_cost=ManaCost.parse(mana_cost_str),
    )


def _make_instant(name: str, mana_cost_str: str) -> Instant:
    """Create a simple instant with the given mana cost."""
    return Instant(
        name=name,
        mana_cost=ManaCost.parse(mana_cost_str),
    )


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery) or CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_subtypes_include_lesson(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes


class TestImprovisationCapstoneExileEffect:
    """The primary effect: exile cards from top of library until total MV >= 4."""

    def test_exiles_cards_until_total_mv_reaches_four(self) -> None:
        """With four 1-MV cards on top, all four should be exiled to reach MV 4."""
        game = create_game()
        p1 = game.players[0]

        # Stack library: bottom -> top: card_a(1), card_b(1), card_c(1), card_d(1)
        card_a = _make_creature("Card A", "{R}")  # MV 1
        card_b = _make_creature("Card B", "{R}")  # MV 1
        card_c = _make_creature("Card C", "{R}")  # MV 1
        card_d = _make_creature("Card D", "{R}")  # MV 1

        library = game.get_library(p1)
        for c in [card_a, card_b, card_c, card_d]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Script: decline to cast all exiled spells
        p1._script.extend([False, False, False, False])

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_cards = exile.get_all()
        exiled_names = {getattr(c, "name", "") for c in exiled_cards}

        # All four 1-MV cards should be exiled to reach total MV 4
        assert "Card D" in exiled_names
        assert "Card C" in exiled_names
        assert "Card B" in exiled_names
        assert "Card A" in exiled_names

    def test_stops_exiling_once_mv_threshold_met(self) -> None:
        """A single 4-MV card on top should cause only one card to be exiled."""
        game = create_game()
        p1 = game.players[0]

        big_card = _make_creature("Big Card", "{3}{R}")  # MV 4
        extra_card = _make_creature("Extra Card", "{R}")  # MV 1 (should NOT be exiled)

        library = game.get_library(p1)
        # Bottom -> top: extra, big
        extra_card.owner = p1
        extra_card.controller = p1
        library.add(extra_card)
        big_card.owner = p1
        big_card.controller = p1
        library.add(big_card)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Script: decline to cast the exiled spell
        p1._script.extend([False])

        spell.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", "") for c in exile.get_all()}
        assert "Big Card" in exiled_names
        # Extra card should remain in library
        lib_names = {getattr(c, "name", "") for c in library.get_all()}
        assert "Extra Card" in lib_names

    def test_mv_five_exceeds_threshold_stops(self) -> None:
        """A single 5-MV card exceeds the threshold of 4; should stop after one exile."""
        game = create_game()
        p1 = game.players[0]

        big = _make_creature("Huge Card", "{4}{R}")  # MV 5
        small = _make_creature("Small Card", "{R}")  # MV 1

        library = game.get_library(p1)
        small.owner = p1
        small.controller = p1
        library.add(small)
        big.owner = p1
        big.controller = p1
        library.add(big)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([False])
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", "") for c in exile.get_all()}
        assert "Huge Card" in exiled_names
        assert "Small Card" not in exiled_names

    def test_zero_mv_cards_do_not_count_toward_threshold(self) -> None:
        """Cards with MV 0 should be exiled but not count toward the total MV 4."""
        game = create_game()
        p1 = game.players[0]

        # Stack: bottom -> top: MV-4 creature, MV-0 creature, MV-0 creature
        zero_a = _make_creature("Zero A", "{0}")  # MV 0
        zero_b = _make_creature("Zero B", "{0}")  # MV 0
        four_card = _make_creature("Four Card", "{3}{R}")  # MV 4

        library = game.get_library(p1)
        for c in [four_card, zero_b, zero_a]:
            # bottom: four_card, then zero_b, then zero_a on top
            # Exiling from top: zero_a (total 0), zero_b (total 0), four_card (total 4) - stop
            c.owner = p1
            c.controller = p1
            library.add(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Decline all casts
        p1._script.extend([False, False, False])
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", "") for c in exile.get_all()}
        # All three should be exiled since we need to reach MV 4
        assert "Zero A" in exiled_names
        assert "Zero B" in exiled_names
        assert "Four Card" in exiled_names

    def test_empty_library_does_not_crash(self) -> None:
        """If the library is empty, resolving should not crash.
        Also verifies that Paradigm behavior still triggers even with empty library."""
        game = create_game()
        p1 = game.players[0]

        # Library is empty by default from create_game
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Should complete without error
        spell.on_resolve(game)

        # Paradigm should still register a delayed trigger even when library is empty
        triggers = game.trigger_manager.get_triggers()
        assert len(triggers) > 0, (
            "Paradigm delayed trigger should be registered even with empty library"
        )

    def test_library_exhausted_before_threshold(self) -> None:
        """If library runs out before reaching MV 4, exile what's available."""
        game = create_game()
        p1 = game.players[0]

        # Only 2 MV worth of cards
        small_a = _make_creature("Small A", "{R}")  # MV 1
        small_b = _make_creature("Small B", "{R}")  # MV 1

        library = game.get_library(p1)
        for c in [small_a, small_b]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Decline to cast
        p1._script.extend([False, False])
        spell.on_resolve(game)

        # Both should be exiled even though MV 4 wasn't reached
        exile = game.get_exile(p1)
        assert len([c for c in exile.get_all() if getattr(c, "name", "").startswith("Small")]) == 2
        # Library should be empty
        assert len(library) == 0


class TestImprovisationCapstoneCasting:
    """You may cast any number of spells from among exiled cards without paying mana costs."""

    def test_cast_exiled_spell_without_paying_mana(self) -> None:
        """When choosing to cast an exiled spell, it should resolve without mana payment."""
        game = create_game()
        p1 = game.players[0]

        # A single 4-MV creature on top of library
        creature = _make_creature("Free Cast Target", "{3}{R}", power=4, toughness=4)

        library = game.get_library(p1)
        creature.owner = p1
        creature.controller = p1
        library.add(creature)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Script: choose to cast the creature
        p1._script.extend([True])
        spell.on_resolve(game)

        # The creature should be on the battlefield (or at least not just in exile)
        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        assert "Free Cast Target" in bf_names

    def test_choose_not_to_cast_leaves_in_exile(self) -> None:
        """When declining to cast, the exiled card should stay in exile."""
        game = create_game()
        p1 = game.players[0]

        creature = _make_creature("Declined Card", "{3}{R}", power=3, toughness=3)

        library = game.get_library(p1)
        creature.owner = p1
        creature.controller = p1
        library.add(creature)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Script: decline to cast
        p1._script.extend([False])
        spell.on_resolve(game)

        # The card should remain in exile
        exile = game.get_exile(p1)
        exile_names = [getattr(c, "name", "") for c in exile.get_all()]
        assert "Declined Card" in exile_names

        # And NOT on the battlefield
        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        assert "Declined Card" not in bf_names

    def test_can_cast_multiple_spells_from_exiled(self) -> None:
        """You may cast any number of spells from among the exiled cards."""
        game = create_game()
        p1 = game.players[0]

        # Stack library with 2-MV creatures to reach threshold of 4
        c1 = _make_creature("Cast Me 1", "{1}{R}", power=2, toughness=2)  # MV 2
        c2 = _make_creature("Cast Me 2", "{1}{R}", power=2, toughness=2)  # MV 2

        library = game.get_library(p1)
        for c in [c1, c2]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Script: choose to cast both
        p1._script.extend([True, True])
        spell.on_resolve(game)

        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        assert "Cast Me 1" in bf_names
        assert "Cast Me 2" in bf_names

    def test_lands_among_exiled_cannot_be_cast(self) -> None:
        """Lands are not spells, so they cannot be cast from among the exiled cards."""
        from engine.card import Land

        game = create_game()
        p1 = game.players[0]

        # A land with MV 0 and a 4-MV creature
        land = Land(name="Mountain")
        land.mana_cost = ManaCost()  # MV 0
        big = _make_creature("Big Guy", "{3}{R}")  # MV 4

        library = game.get_library(p1)
        # bottom: big, top: land
        # Exile from top: land (MV 0, total 0), big (MV 4, total 4) -> stop
        for c in [big, land]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Script: cast the creature only (land should not be offered)
        # If land is offered, we decline; if creature is offered, we decline too
        p1._script.extend([False, False])
        spell.on_resolve(game)

        # Both should be in exile
        exile = game.get_exile(p1)
        exile_names = [getattr(c, "name", "") for c in exile.get_all()]
        assert "Mountain" in exile_names

        # Land should NOT be on the battlefield
        bf = game.get_battlefield(p1)
        bf_names = [getattr(c, "name", "") for c in bf.get_all()]
        assert "Mountain" not in bf_names


class TestImprovisationCapstoneParadigm:
    """Paradigm: exile this spell after resolving, and create delayed trigger."""

    def test_spell_is_exiled_after_resolution(self) -> None:
        """Paradigm says 'Exile this spell' — after resolution it should be in exile,
        not the graveyard."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)

        # Put the spell on the stack zone to simulate resolution
        p1.zones[Zone.STACK].add(spell)

        # Give it an empty library so the exile effect is a no-op
        # (library is empty by default)

        spell.on_resolve(game)

        # After on_resolve, the spell should move to exile
        # The casting pipeline handles the zone move, but the card's paradigm
        # should ensure exile instead of graveyard. We check that the card
        # indicates it should be exiled.
        # Check for the exile marker or that the card is in exile
        exile = game.get_exile(p1)
        graveyard = game.get_graveyard(p1)

        # The spell should be in exile, not in graveyard
        # (Note: the casting pipeline's _resolve_spell handles the actual move,
        # but the card should set up the exile-instead marker like _dawning_archaic_exile
        # or the on_resolve should move it directly)
        in_exile = exile.contains(spell)
        has_exile_marker = getattr(spell, "_paradigm_exile", False) or getattr(spell, "_dawning_archaic_exile", False)
        # At least one of these should be true after on_resolve
        assert in_exile or has_exile_marker, (
            "Spell should be in exile or have an exile marker after resolution (Paradigm)"
        )

    def test_paradigm_first_resolution_registers_delayed_trigger(self) -> None:
        """After the first resolution, Paradigm should register a delayed trigger
        that fires at the beginning of each precombat main phase."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)

        triggers_before = len(game.trigger_manager.get_triggers())

        spell.on_resolve(game)

        triggers_after = len(game.trigger_manager.get_triggers())

        # There should be at least one new trigger registered for the paradigm
        assert triggers_after > triggers_before, (
            "Paradigm should register a delayed trigger after first resolution"
        )

    def test_paradigm_second_resolution_does_not_double_register(self) -> None:
        """Paradigm text says 'After you first resolve a spell with this name' --
        the delayed trigger is set up only once, not on each resolution."""
        game = create_game()
        p1 = game.players[0]

        spell1 = ImprovisationCapstone(owner=p1, controller=p1)
        spell2 = ImprovisationCapstone(owner=p1, controller=p1)

        spell1.on_resolve(game)
        triggers_after_first = len(game.trigger_manager.get_triggers())

        # First resolution must have registered at least one trigger (paradigm)
        assert triggers_after_first > 0, (
            "First resolution should register a paradigm delayed trigger"
        )

        spell2.on_resolve(game)
        triggers_after_second = len(game.trigger_manager.get_triggers())

        # The trigger count should not increase on the second resolution
        assert triggers_after_second == triggers_after_first, (
            "Paradigm delayed trigger should only be registered once (on first resolution)"
        )


class TestImprovisationCapstoneExileFromTop:
    """Verify the exile operates on the top of the library."""

    def test_exiles_from_top_not_bottom(self) -> None:
        """Cards should be exiled from the top of the library (last in the list)."""
        game = create_game()
        p1 = game.players[0]

        # Stack: bottom card (MV 4) and top card (MV 1)
        bottom = _make_creature("Bottom Card", "{3}{R}")  # MV 4
        top = _make_creature("Top Card", "{R}")  # MV 1

        library = game.get_library(p1)
        # Add bottom first, then top (top is last = top of library)
        bottom.owner = p1
        bottom.controller = p1
        library.add(bottom)
        top.owner = p1
        top.controller = p1
        library.add(top)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([False, False])
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", "") for c in exile.get_all()}

        # Top Card (MV 1) should be exiled first, then Bottom Card (MV 4)
        # Total: 1 + 4 = 5 >= 4, so both get exiled
        assert "Top Card" in exiled_names
        assert "Bottom Card" in exiled_names

    def test_partial_threshold_exiles_correct_cards(self) -> None:
        """With a 3-MV card on top and a 2-MV card below, both should be exiled
        (total MV 5 >= 4), and a 1-MV card below that should NOT be exiled."""
        game = create_game()
        p1 = game.players[0]

        bottom = _make_creature("Bottom Stay", "{R}")   # MV 1 -- should stay
        middle = _make_creature("Middle", "{1}{R}")      # MV 2
        top = _make_creature("Top", "{2}{R}")             # MV 3

        library = game.get_library(p1)
        for c in [bottom, middle, top]:
            c.owner = p1
            c.controller = p1
            library.add(c)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([False, False])
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        exiled_names = {getattr(c, "name", "") for c in exile.get_all()}

        # Top (MV 3) exiled first (total 3 < 4), then Middle (MV 2) exiled (total 5 >= 4) -- stop
        assert "Top" in exiled_names
        assert "Middle" in exiled_names
        assert "Bottom Stay" not in exiled_names

        # Bottom Stay should still be in library
        lib_names = {getattr(c, "name", "") for c in library.get_all()}
        assert "Bottom Stay" in lib_names


class TestImprovisationCapstoneManaCostForCMC:
    """Verify the card has the correct converted mana cost for the spell itself."""

    def test_cmc_is_seven(self) -> None:
        """Mana cost {5}{R}{R} should have CMC/mana value of 7."""
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7
