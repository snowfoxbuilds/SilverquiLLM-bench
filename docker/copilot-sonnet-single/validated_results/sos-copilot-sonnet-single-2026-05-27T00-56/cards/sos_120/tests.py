"""Tests for sos_120 — Improvisation Capstone.

Improvisation Capstone is a {5}{R}{R} Sorcery — Lesson with two clause groups:

Main effect:
  "Exile cards from the top of your library until you exile cards with total
   mana value 4 or greater. You may cast any number of spells from among them
   without paying their mana costs."

Paradigm keyword (RULEBOOK 702.192a):
  "Then exile this spell."
  "If this is the first time a spell you control with this spell's name has
   resolved this game, at the beginning of each of your precombat main phases
   for the rest of the game, create a copy of this object in exile. You may
   cast the copy without paying its mana cost."
"""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helper: build a card with a known mana cost for library setup
# ---------------------------------------------------------------------------

def _make_card(name: str, cmc: int) -> CardImpl:
    """Return a stub CardImpl with the given name and a pure-generic mana cost."""
    card = CardImpl(
        name=name,
        mana_cost=ManaCost.parse(f"{{{cmc}}}") if cmc > 0 else ManaCost(),
        card_types={CardType.INSTANT},
    )
    return card


# ===========================================================================
# 1. Static card properties
# ===========================================================================

class TestImprovisationCapstoneProperties:
    """Static card data should match the sos_120 spec."""

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_mana_cost_cmc_is_7(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_card_type_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types


# ===========================================================================
# 2. Library exile mechanic
# ===========================================================================

class TestImprovisationCapstoneLibraryExile:
    """on_resolve exiles cards from the top of the library until total MV >= 4."""

    def test_empty_library_does_not_crash(self) -> None:
        """Resolving with an empty library is a legal no-op for the exile clause."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)
        # Library is empty (default from create_game).
        card.on_resolve(game)  # Must not raise.

    def test_stops_exiling_when_total_mv_reaches_4(self) -> None:
        """Exiles exactly enough cards so total MV >= 4, then stops."""
        game = create_game()
        p1 = game.players[0]

        # Library: MV-2, MV-2 (total = 4 after two cards → stop).
        c1 = _make_card("Spell-A", 2)
        c2 = _make_card("Spell-B", 2)
        c3 = _make_card("Extra-C", 3)  # Should NOT be exiled.
        # Add bottom-to-top: c3 is bottom, c1 is top.
        lib = game.get_library(p1)
        lib.add(c3)
        lib.add(c2)
        lib.add(c1)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        # c1 and c2 exiled (total MV = 4).
        assert exile.contains(c1)
        assert exile.contains(c2)
        # c3 stays in library (MV threshold already met).
        assert not exile.contains(c3)
        assert lib.contains(c3)

    def test_exiled_cards_removed_from_library(self) -> None:
        """Cards exiled from the library are no longer in the library."""
        game = create_game()
        p1 = game.players[0]

        c1 = _make_card("Big-Spell", 4)  # MV = 4 → stop immediately.
        game.get_library(p1).add(c1)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        assert not game.get_library(p1).contains(c1)

    def test_exiled_cards_in_exile_zone(self) -> None:
        """Cards exiled by the effect appear in the controller's exile zone."""
        game = create_game()
        p1 = game.players[0]

        c1 = _make_card("Big-Spell", 5)  # MV 5 >= 4.
        game.get_library(p1).add(c1)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        assert game.get_exile(p1).contains(c1)

    def test_single_card_with_mv_gte_4_exiles_only_that_card(self) -> None:
        """A single card with MV >= 4 satisfies the threshold; no more exiled."""
        game = create_game()
        p1 = game.players[0]

        c1 = _make_card("Heavy-Hitter", 6)
        c2 = _make_card("Another-Card", 3)
        lib = game.get_library(p1)
        lib.add(c2)  # bottom
        lib.add(c1)  # top — exiled first

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(c1)
        assert not exile.contains(c2)

    def test_exiles_multiple_small_cards_until_threshold_met(self) -> None:
        """Multiple MV-1 cards need to accumulate until total >= 4."""
        game = create_game()
        p1 = game.players[0]

        # Five MV-1 cards; should exile first four (total = 4).
        cards = [_make_card(f"Tiny-{i}", 1) for i in range(5)]
        lib = game.get_library(p1)
        # Add bottom-to-top so cards[0] is on top.
        for c in reversed(cards):
            lib.add(c)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        # First four should be exiled (MV 1+1+1+1 = 4).
        assert exile.contains(cards[0])
        assert exile.contains(cards[1])
        assert exile.contains(cards[2])
        assert exile.contains(cards[3])
        # Fifth card stays in library.
        assert not exile.contains(cards[4])

    def test_exiles_all_when_library_mv_never_reaches_4(self) -> None:
        """If total library MV is < 4, all cards are exiled (library exhausted)."""
        game = create_game()
        p1 = game.players[0]

        # Two MV-1 cards, total = 2 < 4 — library runs out.
        c1 = _make_card("Spark-1", 1)
        c2 = _make_card("Spark-2", 1)
        lib = game.get_library(p1)
        lib.add(c2)
        lib.add(c1)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(c1)
        assert exile.contains(c2)
        assert len(game.get_library(p1).get_all()) == 0

    def test_mv_0_cards_do_not_contribute_to_threshold(self) -> None:
        """MV-0 cards (e.g., lands or 0-cost spells) count 0 and must not
        prevent termination when combined with actual-cost cards."""
        game = create_game()
        p1 = game.players[0]

        # Stack a MV-0 card, then a MV-4 card. Both should be exiled.
        c0 = _make_card("Zero-Cost", 0)
        c4 = _make_card("Four-Cost", 4)
        lib = game.get_library(p1)
        lib.add(c4)  # bottom
        lib.add(c0)  # top — exiled first (MV 0)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(c0)
        assert exile.contains(c4)


# ===========================================================================
# 3. Paradigm — exile this spell
# ===========================================================================

class TestImprovisationCapstoneParadigmExileSelf:
    """After resolving, the Paradigm keyword causes this spell to be exiled
    (rather than moving to the graveyard as a normal sorcery would)."""

    def test_paradigm_exiles_self_on_resolve(self) -> None:
        """After on_resolve, the card should be in the controller's exile zone."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        # Simulate the card being on the stack (where it lives during casting).
        p1.zones[Zone.STACK].add(card)

        card.on_resolve(game)

        assert game.get_exile(p1).contains(card), (
            "Paradigm requires the spell to be exiled after resolution."
        )

    def test_paradigm_spell_not_in_graveyard_after_resolve(self) -> None:
        """After on_resolve, the Paradigm spell should NOT be in the graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        p1.zones[Zone.STACK].add(card)
        card.on_resolve(game)

        assert not game.get_graveyard(p1).contains(card), (
            "Paradigm says exile this spell — it should not go to graveyard."
        )


# ===========================================================================
# 4. Paradigm — triggered main-phase copy ability
# ===========================================================================

class TestImprovisationCapstoneParadigmTrigger:
    """After the first resolution, a trigger for BeginningOfMainPhaseTriggeredEvent
    should be registered so that a free copy can be offered each turn."""

    def test_paradigm_registers_main_phase_trigger_on_first_resolve(self) -> None:
        """on_resolve should register a trigger for the precombat main phase."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        p1.zones[Zone.STACK].add(card)
        before_count = len(game.trigger_manager._triggers)
        card.on_resolve(game)
        after_count = len(game.trigger_manager._triggers)

        assert after_count > before_count, (
            "Paradigm should register at least one trigger on first resolution."
        )

    def test_paradigm_trigger_watches_main_phase_event(self) -> None:
        """The registered Paradigm trigger must watch BeginningOfMainPhaseTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]
        card = ImprovisationCapstone(owner=p1, controller=p1)

        p1.zones[Zone.STACK].add(card)
        card.on_resolve(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        event_types = {t.event_type for t in triggers}
        assert BeginningOfMainPhaseTriggeredEvent in event_types, (
            "Paradigm trigger must watch BeginningOfMainPhaseTriggeredEvent."
        )

    def test_paradigm_trigger_only_registered_once_on_second_resolve(self) -> None:
        """On subsequent resolutions the trigger count must not grow beyond the
        initial registration (the 'first time' guard in rule 702.192a)."""
        game = create_game()
        p1 = game.players[0]

        card1 = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(card1)
        card1.on_resolve(game)
        count_after_first = len(game.trigger_manager._triggers)

        # Simulate a second copy resolving.
        card2 = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(card2)
        card2.on_resolve(game)
        count_after_second = len(game.trigger_manager._triggers)

        assert count_after_second == count_after_first, (
            "Paradigm should not register additional triggers after first resolution."
        )
