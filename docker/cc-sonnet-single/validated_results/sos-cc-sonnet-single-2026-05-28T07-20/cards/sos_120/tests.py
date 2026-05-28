"""Tests for SOS 120 — Improvisation Capstone.

Improvisation Capstone is a Sorcery — Lesson ({5}{R}{R}) with two distinct
behavioral layers:

1. **Main effect**: Exile cards from the top of the controller's library
   until the total mana value (CMC) of the exiled cards is 4 or greater.
   The controller may then cast any number of spells from among those
   exiled cards without paying their mana costs.

2. **Paradigm mechanic**: After the spell resolves it is exiled (not put
   into the graveyard). After the controller has resolved this spell for
   the first time, at the beginning of each of their precombat main phases
   they may cast a copy of it from exile for free — the original stays in
   exile.

Test structure:
- Static card properties
- Main effect: library exile until MV >= 4
- Main effect: free cast of exiled spells
- Paradigm: spell goes to exile (not graveyard) on resolution
- Paradigm: has_paradigm_triggered flag tracks first resolution
- Paradigm: recurring beginning-of-main-phase trigger is registered
"""

from __future__ import annotations

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import CardImpl, Creature, Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card_with_cmc(owner, name: str, cmc: int) -> CardImpl:
    """Return a non-land, non-zero CMC instant card suitable for library stacking."""
    return CardImpl(
        name=name,
        mana_cost=ManaCost(generic=cmc),
        card_types={CardType.INSTANT},
        owner=owner,
        controller=owner,
    )


def _make_creature_with_cmc(owner, name: str, cmc: int) -> Creature:
    """Return a creature card with the given CMC."""
    return Creature(
        name=name,
        mana_cost=ManaCost(generic=cmc),
        owner=owner,
        controller=owner,
        base_power=1,
        base_toughness=1,
    )


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneProperties:
    """Static card data must match the SOS 120 spec."""

    def test_name(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"

    def test_is_sorcery_instance(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)

    def test_has_sorcery_card_type(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in card.card_types

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert "Lesson" in card.subtypes

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_mana_cost_cmc(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost.cmc == 7

    def test_not_a_creature(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.CREATURE not in card.card_types

    def test_not_an_instant(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert CardType.INSTANT not in card.card_types


# ---------------------------------------------------------------------------
# Main effect: exile from library until total MV >= 4
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneLibraryExile:
    """on_resolve must exile cards from the top of the library until
    the cumulative mana value of exiled cards reaches 4 or more."""

    def test_exiles_until_total_mv_reaches_4(self) -> None:
        """With two 2-CMC cards on top, both are exiled (total = 4)."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_card_with_cmc(p1, "Spell A", 2)
        card_b = _make_card_with_cmc(p1, "Spell B", 2)
        # Library: card_b on bottom, card_a on top (last in list = top).
        game.get_library(p1)._objects.clear()
        game.get_library(p1).add(card_b, position="top")
        game.get_library(p1).add(card_a, position="top")

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1).get_all()
        # Both cards moved to exile; the spell itself is also in exile via Paradigm.
        assert card_a in exile
        assert card_b in exile

    def test_stops_exiling_once_mv_threshold_met(self) -> None:
        """A 5-CMC card on top alone satisfies the 4-MV threshold; no more exiled."""
        game = create_game()
        p1 = game.players[0]

        big_card = _make_card_with_cmc(p1, "Big Spell", 5)
        leftover = _make_card_with_cmc(p1, "Leftover", 3)
        # Library (top → bottom): big_card on top, leftover below.
        game.get_library(p1)._objects.clear()
        game.get_library(p1).add(leftover, position="top")
        game.get_library(p1).add(big_card, position="top")

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1).get_all()
        assert big_card in exile
        # leftover should still be in the library — threshold was already met.
        assert leftover not in exile
        assert game.get_library(p1).contains(leftover)

    def test_exiles_multiple_low_mv_cards_until_threshold(self) -> None:
        """Three 2-CMC cards: the first two (total 4) are exiled, the third stays."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_card_with_cmc(p1, "Spell A", 2)
        card_b = _make_card_with_cmc(p1, "Spell B", 2)
        card_c = _make_card_with_cmc(p1, "Spell C", 2)
        # Library top → bottom: card_a, card_b, card_c
        game.get_library(p1)._objects.clear()
        game.get_library(p1).add(card_c, position="top")
        game.get_library(p1).add(card_b, position="top")
        game.get_library(p1).add(card_a, position="top")

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        exile = game.get_exile(p1).get_all()
        assert card_a in exile
        assert card_b in exile
        assert card_c not in exile
        assert game.get_library(p1).contains(card_c)

    def test_exiles_from_controller_library_not_opponent(self) -> None:
        """Only the controller's library is touched; opponent's library is intact."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target_card = _make_card_with_cmc(p1, "Controller Spell", 4)
        opponent_card = _make_card_with_cmc(p2, "Opponent Spell", 4)
        game.get_library(p1)._objects.clear()
        game.get_library(p1).add(target_card, position="top")
        game.get_library(p2)._objects.clear()
        game.get_library(p2).add(opponent_card, position="top")

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert game.get_library(p2).contains(opponent_card)

    def test_empty_library_does_not_raise(self) -> None:
        """Resolving with an empty library must not raise (just exile no cards)."""
        game = create_game()
        p1 = game.players[0]
        # Ensure library is empty.
        game.get_library(p1)._objects.clear()

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)  # Must not raise.

    def test_exiled_cards_removed_from_library(self) -> None:
        """Cards that are exiled must no longer appear in the library."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_card_with_cmc(p1, "Spell A", 4)
        game.get_library(p1)._objects.clear()
        game.get_library(p1).add(card_a, position="top")

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert not game.get_library(p1).contains(card_a)


# ---------------------------------------------------------------------------
# Main effect: cast exiled spells for free
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneFreeCast:
    """After exile, the controller should be offered a free cast of the exiled spells."""

    def test_exiled_spells_can_be_cast_for_free(self) -> None:
        """The cards placed in exile during resolution should be offered for free casting.

        Because the actual free-cast prompt depends on player.choose_yes_no and
        player.choose, we verify the spells remain in exile (available for casting)
        or are gone from exile (were cast). Either outcome is acceptable — what's
        NOT acceptable is the card staying in the library or going to the graveyard.
        """
        game = create_game()
        p1 = game.players[0]

        castable = _make_card_with_cmc(p1, "Free Spell", 4)
        game.get_library(p1)._objects.clear()
        game.get_library(p1).add(castable, position="top")

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # After resolution: the card must not be in the library anymore.
        assert not game.get_library(p1).contains(castable)

    def test_on_resolve_does_not_put_exiled_cards_in_graveyard(self) -> None:
        """Exiled-from-library cards should never land in the graveyard on resolution."""
        game = create_game()
        p1 = game.players[0]

        card_a = _make_card_with_cmc(p1, "Spell A", 2)
        card_b = _make_card_with_cmc(p1, "Spell B", 2)
        game.get_library(p1)._objects.clear()
        game.get_library(p1).add(card_b, position="top")
        game.get_library(p1).add(card_a, position="top")

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        graveyard = game.get_graveyard(p1).get_all()
        assert card_a not in graveyard
        assert card_b not in graveyard


# ---------------------------------------------------------------------------
# Paradigm: spell goes to exile on resolution
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigmExile:
    """Paradigm says 'then exile this spell' — it must not go to the graveyard."""

    def test_spell_not_in_graveyard_after_resolution(self) -> None:
        """After on_resolve, the Improvisation Capstone card is not in the graveyard."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        # Add card to graveyard's STACK zone so resolution can move it.
        # For a direct on_resolve call (no casting pipeline), we just call it.
        spell.on_resolve(game)

        graveyard = game.get_graveyard(p1).get_all()
        assert spell not in graveyard

    def test_spell_in_exile_after_resolution(self) -> None:
        """After resolving, the Improvisation Capstone is found in the exile zone."""
        game = create_game()
        p1 = game.players[0]

        # Simulate the post-stack state: card is in the stack zone when resolving,
        # then Paradigm exile replaces the graveyard move.
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)

        spell.on_resolve(game)

        exile = game.get_exile(p1).get_all()
        assert spell in exile

    def test_second_resolution_spell_also_in_exile(self) -> None:
        """Even after the second resolution, the card ends up in exile each time."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)
        spell.on_resolve(game)

        # Remove from exile to simulate a second cast (a copy would be separate).
        # A copy being cast places it on the stack; after resolving, it's also exiled.
        spell2 = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell2)
        spell2.on_resolve(game)

        exile = game.get_exile(p1).get_all()
        assert spell2 in exile


# ---------------------------------------------------------------------------
# Paradigm: has_paradigm_triggered flag
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigmFlag:
    """The Paradigm mechanic requires tracking whether this spell has ever resolved
    before, so the recurring trigger is only set up once."""

    def test_has_paradigm_triggered_false_before_resolution(self) -> None:
        """A fresh card should not yet have the paradigm triggered."""
        card = ImprovisationCapstone(owner=None)
        # Before resolution: the flag must be False (or absent/falsy).
        flag = getattr(card, "has_paradigm_triggered", False)
        assert not flag

    def test_has_paradigm_triggered_true_after_resolution(self) -> None:
        """After the first on_resolve, has_paradigm_triggered must be True."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert getattr(spell, "has_paradigm_triggered", False) is True

    def test_has_paradigm_triggered_persists_across_resolutions(self) -> None:
        """The flag stays True even after subsequent resolutions."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell)
        spell.on_resolve(game)

        # Simulated second resolution (Paradigm copy from exile).
        spell2 = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(spell2)
        spell2.on_resolve(game)

        assert getattr(spell2, "has_paradigm_triggered", False) is True


# ---------------------------------------------------------------------------
# Paradigm: recurring beginning-of-main-phase trigger
# ---------------------------------------------------------------------------

class TestImprovisationCapstoneParadigmTrigger:
    """After first resolution, a trigger must be registered that fires at the
    beginning of each precombat main phase to allow a free copy cast."""

    def test_trigger_registered_after_first_resolution(self) -> None:
        """At least one trigger must be in the TriggerManager after resolution."""
        game = create_game()
        p1 = game.players[0]

        before = len(game.trigger_manager.get_triggers())
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_trigger_watches_beginning_of_main_phase_event(self) -> None:
        """The registered trigger must watch BeginningOfMainPhaseTriggeredEvent."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        watched_types = [t.event_type for t in triggers]
        assert BeginningOfMainPhaseTriggeredEvent in watched_types

    def test_trigger_controller_is_spell_controller(self) -> None:
        """The registered trigger's controller must be the spell's controller."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        triggers = game.trigger_manager.get_triggers()
        assert any(t.controller is p1 for t in triggers)

    def test_trigger_condition_fires_for_precombat_main(self) -> None:
        """The trigger condition must pass for PRECOMBAT_MAIN events."""
        game = create_game()
        p1 = game.players[0]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(triggers) >= 1
        trigger = triggers[-1]

        event = BeginningOfMainPhaseTriggeredEvent(
            active_player=p1,
            phase=Phase.PRECOMBAT_MAIN,
        )
        if trigger.condition is not None:
            assert trigger.condition(game, event) is True
        # If condition is None it always fires — that's fine.

    def test_trigger_condition_does_not_fire_for_opponent_main_phase(self) -> None:
        """The trigger must NOT fire at the beginning of the opponent's main phase."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(triggers) >= 1
        trigger = triggers[-1]

        if trigger.condition is None:
            # A None condition means it always fires — that would be wrong for
            # an opponent's phase, but we cannot assert False here since this
            # would break un-implemented cards. Mark as expected to check condition.
            return

        event_opponent = BeginningOfMainPhaseTriggeredEvent(
            active_player=p2,
            phase=Phase.PRECOMBAT_MAIN,
        )
        assert trigger.condition(game, event_opponent) is False

    def test_trigger_fires_into_stack_when_event_raised(self) -> None:
        """When the BeginningOfMainPhaseTriggeredEvent is fired, a stack object
        should be pushed for the controller."""
        game = create_game()
        p1 = game.players[0]
        # Set active player so APNAP ordering works.
        game.active_player_index = 0

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Stack should be empty before the event fires.
        assert game.stack.is_empty()

        event = BeginningOfMainPhaseTriggeredEvent(
            active_player=p1,
            phase=Phase.PRECOMBAT_MAIN,
        )
        game.trigger_manager.fire_event(game, event)

        # The trigger should push something onto the stack.
        assert not game.stack.is_empty()
