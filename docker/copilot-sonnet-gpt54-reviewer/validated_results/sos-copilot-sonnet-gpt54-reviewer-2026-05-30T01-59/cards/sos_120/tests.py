"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from collections import deque
from typing import Any

import pytest

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_stack(game: Any) -> None:
    """Drain the stack completely (LIFO order)."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _make_instant(name: str = "Test Instant", cmc: int = 2) -> Instant:
    return Instant(name=name, mana_cost=ManaCost(generic=cmc))


def _make_sorcery(name: str = "Test Sorcery", cmc: int = 3) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost(generic=cmc))


def _make_creature(name: str = "Test Creature", cmc: int = 3) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost(generic=cmc),
        base_power=2,
        base_toughness=2,
    )


def _populate_library(game: Any, player: Any, cards: list[Any]) -> None:
    """Place cards in library with first card on top (last added = top)."""
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    # Add in reverse order so cards[0] ends up on top
    for card in reversed(cards):
        card.owner = player
        card.controller = player
        lib.add(card, position="top")  # each pushed to top


# ---------------------------------------------------------------------------
# 1. Card Identity
# ---------------------------------------------------------------------------


class TestImprovisationCapstoneIdentity:
    def test_name(self) -> None:
        card = ImprovisationCapstone()
        assert card.name == "Improvisation Capstone"

    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone()
        assert CardType.SORCERY in card.card_types

    def test_not_instant(self) -> None:
        card = ImprovisationCapstone()
        assert CardType.INSTANT not in card.card_types

    def test_has_lesson_subtype(self) -> None:
        card = ImprovisationCapstone()
        assert "Lesson" in card.subtypes

    def test_mana_cost(self) -> None:
        card = ImprovisationCapstone()
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_cmc_is_seven(self) -> None:
        card = ImprovisationCapstone()
        assert card.mana_cost.cmc == 7

    def test_is_sorcery_instance(self) -> None:
        card = ImprovisationCapstone()
        assert isinstance(card, Sorcery)


# ---------------------------------------------------------------------------
# 2. Main Effect — exile from library until total MV >= 4
# ---------------------------------------------------------------------------


class TestMainEffectExile:
    def test_exiles_cards_until_total_mv_four(self) -> None:
        """Exiles top cards until total MV reaches 4; stops exactly there."""
        game = create_game()
        p1 = game.players[0]

        # Cards on top (in order): cmc1=1, cmc2=1, cmc3=2, cmc4=5
        # Exile cmc1 (mv=1 < 4), exile cmc2 (mv=2 < 4), exile cmc3 (mv=4 >= 4 → stop)
        cmc1 = _make_instant("A1", cmc=1)
        cmc2 = _make_instant("A2", cmc=1)
        cmc3 = _make_instant("A3", cmc=2)
        cmc4 = _make_instant("A4", cmc=5)

        _populate_library(game, p1, [cmc1, cmc2, cmc3, cmc4])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        # Decline to cast any exiled card
        p1._script = deque([False, False, False])
        ic.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(cmc1)
        assert exile.contains(cmc2)
        assert exile.contains(cmc3)
        assert not exile.contains(cmc4)  # not reached

    def test_single_card_with_mv_four_stops_immediately(self) -> None:
        """A single card with MV 4 satisfies the threshold immediately."""
        game = create_game()
        p1 = game.players[0]

        card_mv4 = _make_instant("Exact4", cmc=4)
        card_next = _make_instant("Next", cmc=2)

        _populate_library(game, p1, [card_mv4, card_next])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script = deque([False])
        ic.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(card_mv4)
        assert not exile.contains(card_next)

    def test_empty_library_does_not_crash(self) -> None:
        """Resolving with empty library simply exiles nothing."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        ic.on_resolve(game)  # should not raise

        exile = game.get_exile(p1)
        assert len(exile) == 0

    def test_exiled_cards_removed_from_library(self) -> None:
        """Exiled cards are no longer in the library."""
        game = create_game()
        p1 = game.players[0]

        card_mv5 = _make_instant("Big", cmc=5)
        _populate_library(game, p1, [card_mv5])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script = deque([False])
        ic.on_resolve(game)

        lib = game.get_library(p1)
        assert not lib.contains(card_mv5)

    def test_mv_accumulates_across_multiple_cards(self) -> None:
        """Total MV is correctly summed across multiple cards."""
        game = create_game()
        p1 = game.players[0]

        # 4 cards each with MV 1 → total exactly 4 after all 4 exiled
        cards = [_make_instant(f"C{i}", cmc=1) for i in range(4)]
        extra = _make_instant("Extra", cmc=3)

        _populate_library(game, p1, cards + [extra])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script = deque([False] * 4)  # decline all 4
        ic.on_resolve(game)

        exile = game.get_exile(p1)
        for c in cards:
            assert exile.contains(c)
        assert not exile.contains(extra)

    def test_zero_mv_cards_are_exiled_but_do_not_count(self) -> None:
        """Cards with MV 0 are exiled but don't contribute to the threshold."""
        game = create_game()
        p1 = game.players[0]

        zero_mv = Instant(name="ZeroMV", mana_cost=ManaCost(generic=0))
        real_mv = _make_instant("RealMV", cmc=4)

        _populate_library(game, p1, [zero_mv, real_mv])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script = deque([False, False])
        ic.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(zero_mv)
        assert exile.contains(real_mv)


# ---------------------------------------------------------------------------
# 3. Cast exiled cards for free
# ---------------------------------------------------------------------------


class TestCastExiledForFree:
    def test_player_may_cast_exiled_spell_for_free(self) -> None:
        """Answering yes causes the exiled card to be cast for free (on stack)."""
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        card_to_cast = _make_instant("FreeSpell", cmc=3)
        _populate_library(game, p1, [card_to_cast])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        # Say YES to casting the exiled card
        p1._script = deque([True])
        ic.on_resolve(game)

        # The exiled card should now be on the stack (cast for free)
        assert not game.stack.is_empty()
        top_obj = game.stack.peek()
        assert top_obj.source is card_to_cast

    def test_player_may_decline_to_cast(self) -> None:
        """Answering no leaves the card in exile and off the stack."""
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        card_stay = _make_instant("Staying", cmc=4)
        _populate_library(game, p1, [card_stay])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script = deque([False])
        ic.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(card_stay)
        assert game.stack.is_empty()

    def test_land_cards_are_not_offered_for_casting(self) -> None:
        """Lands exiled by the main effect cannot be cast (they are lands)."""
        from engine.card import Land

        game = create_game()
        p1 = game.players[0]

        land_card = Land(name="TestLand", owner=p1, controller=p1)
        spell_card = _make_instant("Spell", cmc=4)

        _populate_library(game, p1, [land_card, spell_card])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        # Only the spell should be offered; say yes to it
        p1._script = deque([False])
        ic.on_resolve(game)

        exile = game.get_exile(p1)
        assert exile.contains(land_card)

    def test_multiple_exiled_spells_all_offered(self) -> None:
        """Each exiled non-land spell gets a separate yes/no choice."""
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        s1 = _make_instant("Spell1", cmc=2)
        s2 = _make_instant("Spell2", cmc=2)

        _populate_library(game, p1, [s1, s2])

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        # Say yes to first spell, no to second
        p1._script = deque([True, False])
        ic.on_resolve(game)

        exile = game.get_exile(p1)
        # s1 was cast (not in exile), s2 remains in exile
        assert not exile.contains(s1)
        assert exile.contains(s2)
        assert not game.stack.is_empty()


# ---------------------------------------------------------------------------
# 4. Paradigm — this spell goes to exile instead of graveyard
# ---------------------------------------------------------------------------


class TestParadigmExile:
    def test_exile_on_resolve_flag_is_set(self) -> None:
        """on_resolve sets _exile_on_resolve=True so resolution sends it to exile."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        ic.on_resolve(game)

        assert getattr(ic, "_exile_on_resolve", False) is True

    def test_card_does_not_go_to_graveyard_after_resolution(self) -> None:
        """After full resolution pipeline, Improvisation Capstone ends up in exile."""
        from engine.casting import cast_spell_free

        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        exile_zone = game.get_exile(p1)
        exile_zone.add(ic)  # place in exile so cast_spell_free can find it

        p1._script = deque([])  # no yes/no choices needed (empty library)

        cast_spell_free(game, p1, ic, Zone.EXILE)
        _resolve_stack(game)

        graveyard = game.get_graveyard(p1)
        assert not graveyard.contains(ic)
        assert exile_zone.contains(ic)


# ---------------------------------------------------------------------------
# 5. Paradigm — first resolve sets the paradigm flag
# ---------------------------------------------------------------------------


class TestParadigmFirstResolveFlag:
    def test_first_resolve_sets_paradigm_flag(self) -> None:
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        assert not getattr(p1, "_improvisation_capstone_paradigm", False)
        ic.on_resolve(game)
        assert getattr(p1, "_improvisation_capstone_paradigm", False) is True

    def test_second_resolve_does_not_double_register_trigger(self) -> None:
        """Resolving a second copy does not register another trigger."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        initial_trigger_count = len(game.trigger_manager._triggers)

        ic1 = ImprovisationCapstone(owner=p1, controller=p1)
        ic1.on_resolve(game)
        triggers_after_first = len(game.trigger_manager._triggers)

        ic2 = ImprovisationCapstone(owner=p1, controller=p1)
        ic2.on_resolve(game)
        triggers_after_second = len(game.trigger_manager._triggers)

        # Only one new trigger should have been registered (from first resolve)
        assert triggers_after_first > initial_trigger_count
        assert triggers_after_second == triggers_after_first

    def test_paradigm_flag_is_per_player(self) -> None:
        """Each player has their own paradigm flag."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        lib1 = p1.zones[Zone.LIBRARY]
        for c in list(lib1.get_all()):
            lib1.remove(c)
        lib2 = p2.zones[Zone.LIBRARY]
        for c in list(lib2.get_all()):
            lib2.remove(c)

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        ic.on_resolve(game)

        assert getattr(p1, "_improvisation_capstone_paradigm", False) is True
        assert not getattr(p2, "_improvisation_capstone_paradigm", False)


# ---------------------------------------------------------------------------
# 6. Paradigm — copy offered at beginning of each precombat main phase
# ---------------------------------------------------------------------------


class TestParadigmRecurringTrigger:
    def test_trigger_registered_after_first_resolve(self) -> None:
        """After first resolve, a trigger is registered for main phase."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        initial_count = len(game.trigger_manager._triggers)
        ic = ImprovisationCapstone(owner=p1, controller=p1)
        ic.on_resolve(game)

        assert len(game.trigger_manager._triggers) > initial_count

    def test_trigger_fires_at_precombat_main_phase(self) -> None:
        """Trigger fires at controller's precombat main phase."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        # Put an IC in exile so the trigger can find one
        ic_in_exile = ImprovisationCapstone(owner=p1, controller=p1)
        game.get_exile(p1).add(ic_in_exile)

        ic_resolver = ImprovisationCapstone(owner=p1, controller=p1)
        ic_resolver.on_resolve(game)

        # Say yes to the paradigm copy offer
        p1._script = deque([True])
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)

        # A copy should have been placed on the stack and resolved
        # After resolving the copy it goes to exile (Paradigm), and
        # since the flag is already set it won't double-register.
        # The key assertion: the trigger attempted to cast a copy.
        # The copy would have been stacked and resolved via _resolve_stack.
        # After resolution the copy is in exile (not graveyard).
        exile = game.get_exile(p1)
        # We should see at least 2 ICs in exile:
        # the original ic_in_exile + the copy that was cast and exiled
        ic_count = sum(
            1 for c in exile.get_all()
            if getattr(c, "name", "") == "Improvisation Capstone"
        )
        assert ic_count >= 2

    def test_trigger_does_not_fire_for_opponent_main_phase(self) -> None:
        """Trigger does not fire at the opponent's main phase."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic_in_exile = ImprovisationCapstone(owner=p1, controller=p1)
        game.get_exile(p1).add(ic_in_exile)

        ic_resolver = ImprovisationCapstone(owner=p1, controller=p1)
        ic_resolver.on_resolve(game)

        # Fire opponent's main phase — trigger should not fire
        p2._script = deque([])
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p2, phase=Phase.PRECOMBAT_MAIN),
        )
        # Stack should remain empty (no trigger fired)
        assert game.stack.is_empty()

    def test_trigger_does_not_fire_at_postcombat_main_phase(self) -> None:
        """Paradigm only triggers at precombat ('first') main phase, not postcombat."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic_in_exile = ImprovisationCapstone(owner=p1, controller=p1)
        game.get_exile(p1).add(ic_in_exile)

        ic_resolver = ImprovisationCapstone(owner=p1, controller=p1)
        ic_resolver.on_resolve(game)

        # Fire postcombat main phase event
        p1._script = deque([])
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.POSTCOMBAT_MAIN),
        )
        assert game.stack.is_empty()

    def test_trigger_skips_if_no_ic_in_exile(self) -> None:
        """If no Improvisation Capstone is in exile, trigger does nothing."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic_resolver = ImprovisationCapstone(owner=p1, controller=p1)
        ic_resolver.on_resolve(game)

        # No IC in exile → trigger effect should no-op
        p1._script = deque([])
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)
        assert game.stack.is_empty()

    def test_paradigm_copy_is_offered_each_main_phase(self) -> None:
        """The recurring trigger fires on multiple main phase events."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic_in_exile = ImprovisationCapstone(owner=p1, controller=p1)
        game.get_exile(p1).add(ic_in_exile)

        ic_resolver = ImprovisationCapstone(owner=p1, controller=p1)
        ic_resolver.on_resolve(game)

        # First main phase — decline
        p1._script = deque([False])
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)
        assert game.stack.is_empty()

        # Second main phase — accept
        p1._script = deque([True])
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)
        # After resolving the copy, it's in exile (Paradigm)
        exile = game.get_exile(p1)
        ic_count = sum(
            1 for c in exile.get_all()
            if getattr(c, "name", "") == "Improvisation Capstone"
        )
        assert ic_count >= 2


# ---------------------------------------------------------------------------
# 7. Second+ resolve does not stack effect
# ---------------------------------------------------------------------------


class TestParadigmNoDoubleStack:
    def test_second_resolve_does_not_add_another_trigger(self) -> None:
        """Resolving a second Improvisation Capstone leaves trigger count unchanged."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        ic1 = ImprovisationCapstone(owner=p1, controller=p1)
        ic1.on_resolve(game)
        count_after_first = len(game.trigger_manager._triggers)

        ic2 = ImprovisationCapstone(owner=p1, controller=p1)
        ic2.on_resolve(game)
        count_after_second = len(game.trigger_manager._triggers)

        assert count_after_second == count_after_first

    def test_paradigm_flag_prevents_duplicate_registration(self) -> None:
        """The _improvisation_capstone_paradigm flag stops duplicate triggers."""
        game = create_game()
        p1 = game.players[0]

        lib = p1.zones[Zone.LIBRARY]
        for c in list(lib.get_all()):
            lib.remove(c)

        # Pre-set the flag as if first resolve already happened
        p1._improvisation_capstone_paradigm = True  # type: ignore[attr-defined]

        ic = ImprovisationCapstone(owner=p1, controller=p1)
        count_before = len(game.trigger_manager._triggers)
        ic.on_resolve(game)
        count_after = len(game.trigger_manager._triggers)

        assert count_after == count_before  # no new trigger registered
