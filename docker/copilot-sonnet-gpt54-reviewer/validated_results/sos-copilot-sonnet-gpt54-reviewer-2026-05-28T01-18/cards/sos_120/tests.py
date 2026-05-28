"""Tests for SOS 120 — Improvisation Capstone.

Covers:
- Static card properties (name, mana cost, type Sorcery, subtype Lesson)
- Main effect: exiles cards from library until total mana value >= 4
- Main effect: stops exiling once threshold is reached (not all cards)
- Main effect: a single card with MV >= 4 satisfies the threshold alone
- Main effect: graceful handling when library is empty or below threshold
- Paradigm: after on_resolve, card has _exile_on_resolve = True so engine routes to exile
- Paradigm: after first resolution, a BeginningOfMainPhaseTriggeredEvent trigger registered
- Paradigm: trigger is associated with the card's controller
- Paradigm: exiled original remains in exile after main-phase trigger fires
"""

from __future__ import annotations

from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state

from cards.sos.sos_120.card_impl import ImprovisationCapstone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sorcery(name: str, cmc: int, owner=None, controller=None) -> Sorcery:
    """Create a Sorcery with the given CMC for library population."""
    if cmc == 0:
        cost = ManaCost()  # Zero-cost
    else:
        cost = ManaCost.parse("{" + str(cmc) + "}")
    card = Sorcery(name=name, owner=owner, controller=controller, mana_cost=cost)
    return card


def _make_instant(name: str, cmc: int, owner=None, controller=None) -> Instant:
    """Create an Instant with the given CMC for library population."""
    cost = ManaCost.parse("{" + str(cmc) + "}") if cmc > 0 else ManaCost()
    return Instant(name=name, owner=owner, controller=controller, mana_cost=cost)


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneProperties:
    """Static card data must match the SOS 120 spec."""

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_card_type_includes_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_mana_value_is_7(self) -> None:
        """CMC of {5}{R}{R} is 7."""
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7


# ---------------------------------------------------------------------------
# Library exile effect — threshold behavior
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneLibraryExile:
    """on_resolve must exile cards from the top of the library until total MV >= 4."""

    def test_exiles_cards_until_mv_reaches_4(self) -> None:
        """With CMC 2, 2, 1, 1 in library, stops after CMC 2+2=4 (first two)."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_sorcery("CardA", 2, owner=p1, controller=p1)
        card_b = _make_sorcery("CardB", 2, owner=p1, controller=p1)
        card_c = _make_sorcery("CardC", 1, owner=p1, controller=p1)

        library = game.get_library(p1)
        # Top of library is the LAST card added to the ZoneContainer.
        # Build the stack so CardA is on top, then CardB, then CardC.
        library.add(card_c)
        library.add(card_b)
        library.add(card_a)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(card_a), "First card should be exiled"
        assert exile.contains(card_b), "Second card should be exiled (total MV hit 4)"

    def test_stops_exiling_at_threshold(self) -> None:
        """Cards beyond the MV-4 threshold must remain in the library; preceding ones are exiled."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_sorcery("CardA", 2, owner=p1, controller=p1)
        card_b = _make_sorcery("CardB", 2, owner=p1, controller=p1)
        card_c = _make_sorcery("CardC", 1, owner=p1, controller=p1)

        library = game.get_library(p1)
        library.add(card_c)
        library.add(card_b)
        library.add(card_a)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        library_after = game.get_library(p1)

        # The first two cards must have been exiled (total MV = 4)
        assert exile.contains(card_a), "CardA (MV 2) should be exiled"
        assert exile.contains(card_b), "CardB (MV 2, cumulative 4) should be exiled"
        # The third card must remain in the library (threshold already met)
        assert library_after.contains(card_c), "CardC should stay in library (threshold met before it)"
        assert not exile.contains(card_c), "CardC should not be exiled (threshold met)"

    def test_single_card_with_mv_4_satisfies_threshold(self) -> None:
        """A single card with MV exactly 4 satisfies the threshold; nothing more exiled."""
        game = create_game()
        p1 = game.players[0]

        card_big = _make_sorcery("BigCard", 4, owner=p1, controller=p1)
        card_extra = _make_sorcery("ExtraCard", 1, owner=p1, controller=p1)

        library = game.get_library(p1)
        library.add(card_extra)
        library.add(card_big)  # card_big on top

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(card_big), "High-MV card should be exiled"
        assert not exile.contains(card_extra), "Extra card should not be exiled (threshold met)"

    def test_single_card_with_mv_greater_than_4_satisfies_threshold(self) -> None:
        """A single card with MV > 4 satisfies the threshold alone."""
        game = create_game()
        p1 = game.players[0]

        card_big = _make_sorcery("Fireball", 6, owner=p1, controller=p1)
        card_extra = _make_sorcery("Cantrip", 1, owner=p1, controller=p1)

        library = game.get_library(p1)
        library.add(card_extra)
        library.add(card_big)  # card_big on top

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(card_big)
        assert not exile.contains(card_extra)

    def test_exiled_cards_removed_from_library(self) -> None:
        """Cards exiled from library must no longer be in the library."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_sorcery("CardA", 4, owner=p1, controller=p1)

        library = game.get_library(p1)
        library.add(card_a)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert not library.contains(card_a), "Exiled card must not remain in library"

    def test_empty_library_does_not_raise(self) -> None:
        """Resolving when the library is empty must not raise an exception."""
        game = create_game()
        p1 = game.players[0]

        # Library is empty (create_game with no deck sets empty library)
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Should complete without error
        spell.on_resolve(game)

    def test_library_below_threshold_exiles_all_available(self) -> None:
        """If the library runs out before MV 4, all library cards are exiled."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_sorcery("CardA", 1, owner=p1, controller=p1)
        card_b = _make_sorcery("CardB", 1, owner=p1, controller=p1)

        library = game.get_library(p1)
        library.add(card_a)
        library.add(card_b)

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        # Both cards should be exiled (total MV = 2 < 4, but library exhausted)
        assert exile.contains(card_a)
        assert exile.contains(card_b)

    def test_non_spell_cards_count_toward_mv_total(self) -> None:
        """Lands and other non-spells are exiled but have MV 0; exile continues."""
        game = create_game()
        p1 = game.players[0]

        # A basic land has MV 0 — it counts as exiled but adds 0 to the total
        from engine.card import Land
        land = Land(name="Mountain", owner=p1, controller=p1)
        card_big = _make_sorcery("BigSpell", 4, owner=p1, controller=p1)

        library = game.get_library(p1)
        library.add(card_big)  # second (below land)
        library.add(land)      # land is on top

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1)
        # Land was exiled (contributes MV 0), then BigSpell (MV 4) exiled → total 4
        assert exile.contains(land), "Land should be exiled even with MV 0"
        assert exile.contains(card_big), "BigSpell should be exiled (reaches MV threshold)"


# ---------------------------------------------------------------------------
# Paradigm — exile-on-resolve behavior
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmExileOnResolve:
    """After resolution, the card itself must be marked for exile (not graveyard)."""

    def test_exile_on_resolve_flag_set_after_resolution(self) -> None:
        """The card must set _exile_on_resolve = True so the engine routes it to exile."""
        game = create_game()
        p1 = game.players[0]

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        assert getattr(card, "_exile_on_resolve", False) is True, (
            "Paradigm requires _exile_on_resolve = True so the engine sends "
            "the card to exile instead of graveyard after resolution."
        )

    def test_not_exiled_to_graveyard_and_exile_flag_set(self) -> None:
        """Paradigm: card must not be in graveyard AND must have _exile_on_resolve=True after resolution."""
        game = create_game()
        p1 = game.players[0]

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(card), (
            "Paradigm dictates exile, not graveyard, after resolution."
        )
        # The card MUST have set the exile flag (so the engine knows to exile it)
        assert getattr(card, "_exile_on_resolve", False) is True, (
            "Paradigm: card must signal _exile_on_resolve=True to the engine."
        )


# ---------------------------------------------------------------------------
# Paradigm — recurring main-phase trigger registration
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmTrigger:
    """After first resolution, a recurring BeginningOfMainPhaseTriggeredEvent trigger is registered."""

    def test_resolving_registers_beginning_of_main_phase_trigger(self) -> None:
        """on_resolve must register a BeginningOfMainPhaseTriggeredEvent trigger."""
        game = create_game()
        p1 = game.players[0]

        before_count = len(game.trigger_manager._triggers)

        card = ImprovisationCapstone(owner=p1, controller=p1)
        card.on_resolve(game)

        after_count = len(game.trigger_manager._triggers)
        assert after_count > before_count, (
            "Paradigm should register at least one new trigger after first resolution."
        )

        new_triggers = game.trigger_manager._triggers[before_count:]
        event_types = [t.event_type for t in new_triggers]
        assert BeginningOfMainPhaseTriggeredEvent in event_types, (
            "Paradigm trigger must fire at BeginningOfMainPhaseTriggeredEvent."
        )

    def test_trigger_is_controlled_by_resolving_player(self) -> None:
        """The registered trigger's controller should be the card's controller."""
        game = create_game()
        p1 = game.players[0]

        card = ImprovisationCapstone(owner=p1, controller=p1)
        before_count = len(game.trigger_manager._triggers)
        card.on_resolve(game)

        new_triggers = game.trigger_manager._triggers[before_count:]
        main_phase_triggers = [
            t for t in new_triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(main_phase_triggers) >= 1
        assert main_phase_triggers[0].controller is p1, (
            "The Paradigm trigger should be controlled by the card's controller."
        )

    def test_trigger_is_associated_with_card_source(self) -> None:
        """The trigger's source should be the Improvisation Capstone card."""
        game = create_game()
        p1 = game.players[0]

        card = ImprovisationCapstone(owner=p1, controller=p1)
        before_count = len(game.trigger_manager._triggers)
        card.on_resolve(game)

        new_triggers = game.trigger_manager._triggers[before_count:]
        main_phase_triggers = [
            t for t in new_triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(main_phase_triggers) >= 1
        assert main_phase_triggers[0].source is card, (
            "The Paradigm trigger source should be the Improvisation Capstone card."
        )

    def test_trigger_condition_filters_for_controller(self) -> None:
        """The trigger should only fire when the active player is the controller."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = ImprovisationCapstone(owner=p1, controller=p1)
        before_count = len(game.trigger_manager._triggers)
        card.on_resolve(game)

        new_triggers = game.trigger_manager._triggers[before_count:]
        main_phase_triggers = [
            t for t in new_triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(main_phase_triggers) >= 1
        trigger = main_phase_triggers[0]

        event = BeginningOfMainPhaseTriggeredEvent()

        # Trigger should fire for p1 (the controller)
        game.active_player_index = 0
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True, (
                "Trigger condition should return True for the controlling player's main phase."
            )

        # Trigger should NOT fire for p2 (the non-controller)
        game.active_player_index = 1
        if trigger.condition is not None:
            assert trigger.condition(game, event) is False, (
                "Trigger condition should return False for opponent's main phase."
            )


# ---------------------------------------------------------------------------
# Paradigm — exiled original stays after copy effect fires
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneParadigmOriginalPersists:
    """When the main-phase trigger fires and a copy is cast, the original stays in exile."""

    def test_original_card_stays_in_exile_after_trigger_effect(self) -> None:
        """Firing the Paradigm trigger must not remove the original card from exile."""
        game = create_game()
        p1 = game.players[0]

        # Resolve the card to register the trigger
        card = ImprovisationCapstone(owner=p1, controller=p1)
        before_trigger_count = len(game.trigger_manager._triggers)
        card.on_resolve(game)

        # Manually place the card in exile (as if the engine's _exile_on_resolve routed it)
        exile = game.get_exile(p1)
        exile.add(card)

        # Find the BeginningOfMainPhaseTriggeredEvent trigger
        new_triggers = game.trigger_manager._triggers[before_trigger_count:]
        main_phase_triggers = [
            t for t in new_triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(main_phase_triggers) >= 1, "Trigger should have been registered"

        trigger = main_phase_triggers[0]

        # Fire the trigger effect
        trigger.effect(game)

        # The original card must still be in exile (only a copy was cast)
        assert exile.contains(card), (
            "Paradigm: casting the copy must not consume the original exiled card."
        )

    def test_trigger_fires_repeatedly_across_multiple_calls(self) -> None:
        """Paradigm trigger must be persistent (not a one-shot trigger)."""
        game = create_game()
        p1 = game.players[0]

        card = ImprovisationCapstone(owner=p1, controller=p1)
        before_count = len(game.trigger_manager._triggers)
        card.on_resolve(game)
        after_count = len(game.trigger_manager._triggers)

        # The trigger should still be registered after registration (it's recurring)
        main_phase_triggers_after_resolve = [
            t for t in game.trigger_manager._triggers[before_count:]
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(main_phase_triggers_after_resolve) >= 1, (
            "Paradigm trigger should remain registered (recurring, not one-shot)."
        )

        # Place card in exile
        exile = game.get_exile(p1)
        exile.add(card)

        # Fire the trigger once
        trigger = main_phase_triggers_after_resolve[0]
        trigger.effect(game)

        # Trigger should still be registered after firing (recurring, not consumed)
        remaining_triggers = [
            t for t in game.trigger_manager._triggers
            if t.event_type is BeginningOfMainPhaseTriggeredEvent and t.source is card
        ]
        assert len(remaining_triggers) >= 1, (
            "Paradigm trigger should remain registered after firing (not a one-shot)."
        )
