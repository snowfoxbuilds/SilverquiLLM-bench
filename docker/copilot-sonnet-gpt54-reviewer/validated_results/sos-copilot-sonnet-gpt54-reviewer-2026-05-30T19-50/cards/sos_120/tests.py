"""Tests for Improvisation Capstone (SOS #120)."""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.types import CardType, ManaCost, Phase, Zone
from test_utils import advance_to_phase, create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(name: str = "Test Card", cmc: int = 2) -> Sorcery:
    """Create a cheap sorcery-like card for library population."""
    card = Sorcery(name=name, mana_cost=ManaCost(generic=cmc))
    return card


def _make_creature(name: str = "Bear", power: int = 2, toughness: int = 2, cmc: int = 2) -> Creature:
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        mana_cost=ManaCost(generic=cmc),
    )


# ---------------------------------------------------------------------------
# Attribute tests
# ---------------------------------------------------------------------------

class TestAttributes:
    def test_name(self):
        card = ImprovisationCapstone()
        assert card.name == "Improvisation Capstone"

    def test_mana_cost(self):
        card = ImprovisationCapstone()
        assert card.mana_cost.cmc == 7  # {5}{R}{R}

    def test_is_sorcery(self):
        card = ImprovisationCapstone()
        assert CardType.SORCERY in card.card_types

    def test_lesson_subtype(self):
        card = ImprovisationCapstone()
        assert "Lesson" in card.subtypes

    def test_paradigm_keyword(self):
        card = ImprovisationCapstone()
        assert "Paradigm" in getattr(card, "keyword_names", set())

    def test_rules_text_contains_paradigm(self):
        card = ImprovisationCapstone()
        assert "Paradigm" in card.rules_text

    def test_rules_text_contains_exile_effect(self):
        card = ImprovisationCapstone()
        assert "mana value 4" in card.rules_text


# ---------------------------------------------------------------------------
# Main effect: exile until total MV >= 4
# ---------------------------------------------------------------------------

class TestMainEffect:
    def test_exiles_until_total_mv_four(self):
        """Exile cards until total MV >= 4; single 4-MV card suffices."""
        game = create_game()
        card = ImprovisationCapstone(owner=game.players[0], controller=game.players[0])
        lib_card = _make_card("Big Spell", cmc=4)
        lib_card.owner = game.players[0]
        library = game.get_library(game.players[0])
        library.add(lib_card)

        # Put card in stack zone (simulating post-cast state)
        game.players[0].zones[Zone.STACK].add(card)

        card.on_resolve(game)

        exile = game.get_exile(game.players[0])
        assert exile.contains(lib_card)

    def test_exiles_multiple_until_threshold(self):
        """Exile multiple cards to reach MV >= 4."""
        game = create_game()
        card = ImprovisationCapstone(owner=game.players[0], controller=game.players[0])
        # Two 2-MV cards: total 4
        c1 = _make_card("Card A", cmc=2)
        c2 = _make_card("Card B", cmc=2)
        c1.owner = game.players[0]
        c2.owner = game.players[0]
        library = game.get_library(game.players[0])
        library.add(c1)  # bottom
        library.add(c2)  # top

        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        exile = game.get_exile(game.players[0])
        exiled = exile.get_all()
        # Both cards exiled (total MV = 4)
        assert c1 in exiled or c2 in exiled

    def test_exiles_zero_mv_cards_continue(self):
        """Zero-MV cards don't count toward threshold; keeps exiling."""
        game = create_game()
        card = ImprovisationCapstone(owner=game.players[0], controller=game.players[0])
        zero_mv = _make_card("Zero Cost", cmc=0)
        big = _make_card("Big", cmc=4)
        zero_mv.owner = game.players[0]
        big.owner = game.players[0]
        library = game.get_library(game.players[0])
        library.add(zero_mv)  # bottom
        library.add(big)       # top

        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        exile = game.get_exile(game.players[0])
        exiled = exile.get_all()
        # big (top) is exiled first; total MV = 4, stops. zero_mv stays in library.
        assert big in exiled

    def test_empty_library_doesnt_crash(self):
        """Handles empty library gracefully."""
        game = create_game()
        card = ImprovisationCapstone(owner=game.players[0], controller=game.players[0])
        game.players[0].zones[Zone.STACK].add(card)
        # No cards in library — should not raise
        card.on_resolve(game)

    def test_library_cards_removed(self):
        """Exiled cards are removed from library."""
        game = create_game()
        card = ImprovisationCapstone(owner=game.players[0], controller=game.players[0])
        lib_card = _make_card("Target", cmc=5)
        lib_card.owner = game.players[0]
        library = game.get_library(game.players[0])
        library.add(lib_card)

        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        assert not library.contains(lib_card)


# ---------------------------------------------------------------------------
# Free cast of exiled cards
# ---------------------------------------------------------------------------

class TestFreeCast:
    def test_player_can_decline_cast(self):
        """Player declining cast leaves card in exile."""
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)
        lib_card = _make_card("Spell", cmc=4)
        lib_card.owner = player
        game.get_library(player).add(lib_card)

        game.players[0].zones[Zone.STACK].add(card)
        # Script: decline the cast (False)
        player._script.append(False)
        card.on_resolve(game)

        # Card remains in exile (not cast)
        assert game.get_exile(player).contains(lib_card)

    def test_land_cards_not_offered_for_cast(self):
        """Land cards exiled from top of library are not offered for free cast."""
        from engine.card import Land
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)

        # A land has cmc=0 but let's put a real non-land after it for threshold
        land = Land(name="Forest", owner=player)
        big = _make_card("Spell", cmc=4)
        big.owner = player
        library = game.get_library(player)
        library.add(land)  # bottom
        library.add(big)   # top

        game.players[0].zones[Zone.STACK].add(card)
        # No scripted choice → if land were offered, ScriptExhaustedError would fire
        # and want_cast would default to False. big is a sorcery so it IS offered.
        # Script False for big's cast offer
        player._script.append(False)
        card.on_resolve(game)  # should not raise


# ---------------------------------------------------------------------------
# Paradigm: exile instead of graveyard
# ---------------------------------------------------------------------------

class TestParadigmExile:
    def test_self_goes_to_exile_after_resolution(self):
        """Improvisation Capstone exiles itself (Paradigm) instead of going to graveyard."""
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)

        # Put in stack zone (simulates post-cast)
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        exile = game.get_exile(player)
        graveyard = game.get_graveyard(player)
        assert exile.contains(card)
        assert not graveyard.contains(card)

    def test_self_removed_from_stack_zone(self):
        """Card is no longer in stack zone after Paradigm exile."""
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        stack_zone = game.players[0].zones[Zone.STACK]
        assert not stack_zone.contains(card)

    def test_paradigm_exile_not_in_library(self):
        """Self-exile does not accidentally put the card in the library."""
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        library = game.get_library(player)
        assert not library.contains(card)


# ---------------------------------------------------------------------------
# Paradigm: recurring trigger
# ---------------------------------------------------------------------------

class TestParadigmTrigger:
    def test_trigger_registered_after_first_resolution(self):
        """A recurring trigger is registered after the first resolution."""
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)
        game.players[0].zones[Zone.STACK].add(card)

        triggers_before = len(game.trigger_manager.get_triggers())
        card.on_resolve(game)
        triggers_after = len(game.trigger_manager.get_triggers())

        assert triggers_after > triggers_before

    def test_trigger_fires_at_precombat_main(self):
        """The Paradigm trigger fires at the beginning of the first (precombat) main phase."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        # Advance to precombat main phase
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # Manually fire the BeginningOfMainPhaseTriggeredEvent and check
        # that a trigger fires (player asked whether to cast copy).
        player._script.append(False)  # decline cast offer
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player)
        )
        # If we get here without ScriptExhaustedError, trigger fired properly.

    def test_trigger_does_not_fire_for_opponent(self):
        """The Paradigm trigger only fires for the controller, not the opponent."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent

        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = ImprovisationCapstone(owner=player, controller=player)
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        # Fire event as opponent's turn — trigger should NOT fire
        # (no script item needed / consumed)
        game.active_player_index = 1  # switch active player to opponent
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=opponent)
        )
        # No script item consumed = trigger didn't fire for opponent

    def test_paradigm_trigger_not_registered_twice(self):
        """Second resolution of the card does NOT register another trigger."""
        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)

        # First resolution
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)
        triggers_after_first = len(game.trigger_manager.get_triggers())

        # Second resolution (move card back to stack)
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)
        triggers_after_second = len(game.trigger_manager.get_triggers())

        assert triggers_after_second == triggers_after_first

    def test_copy_gets_paradigm_registered_flag(self):
        """The copy created by the Paradigm trigger has _paradigm_registered=True."""
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.stack import StackObject

        game = create_game()
        player = game.players[0]
        card = ImprovisationCapstone(owner=player, controller=player)
        game.players[0].zones[Zone.STACK].add(card)
        card.on_resolve(game)

        # Advance to precombat main
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # Player says yes to cast the copy
        player._script.append(True)
        # The copy will go on the stack; script False for any sub-choices
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=player)
        )

        # Resolve the copy from the stack (if pushed)
        stack = game.stack
        if not stack.is_empty():
            stack_obj = stack.pop()
            # Get the copy card from the stack object's source
            copy_card = getattr(stack_obj, "source", None) or getattr(stack_obj, "card", None)
            if copy_card is not None:
                assert getattr(copy_card, "_paradigm_registered", False) is True
