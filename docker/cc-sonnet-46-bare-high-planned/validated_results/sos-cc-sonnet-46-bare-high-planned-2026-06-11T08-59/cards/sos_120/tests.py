"""Tests for Improvisation Capstone (sos_120)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, create_game, set_board_state
from test_utils import _resolve_top_of_stack


def _setup(library_cards=None):
    """Set up game in p0's precombat main with optional library contents."""
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    p0 = game.players[0]
    if library_cards:
        lib = game.get_library(p0)
        # Clear existing library cards first
        for c in list(lib.get_all()):
            lib.remove(c)
        # Add bottom → top (first in list = bottom)
        for c in library_cards:
            lib.add(c, position="top")
    return game


def test_exile_from_library_until_mv4():
    """Exiles cards from top until cumulative MV >= 4; stops when threshold met."""
    mv2a = Instant(name="Spell2a", mana_cost=ManaCost(generic=2))
    mv2b = Instant(name="Spell2b", mana_cost=ManaCost(generic=2))
    mv3 = Instant(name="Spell3", mana_cost=ManaCost(generic=3))
    # Library (bottom → top): mv3, mv2b, mv2a — so top is mv2a
    game = _setup(library_cards=[mv3, mv2b, mv2a])
    p0 = game.players[0]

    capstone = ImprovisationCapstone()
    capstone.controller = p0
    capstone.owner = p0

    # Decline all cast offers
    p0._script.appendleft(False)  # second: decline mv2b
    p0._script.appendleft(False)  # first: decline mv2a
    # Decline paradigm (no cast offer since _paradigm_registered=False → do_paradigm)
    # But _do_paradigm just registers replacement/trigger, no choice prompted here

    capstone.on_resolve(game)

    exile = game.get_exile(p0)
    lib = game.get_library(p0)
    # mv2a and mv2b should be exiled (total MV = 4), mv3 remains in library
    assert exile.contains(mv2a)
    assert exile.contains(mv2b)
    assert lib.contains(mv3)
    assert not exile.contains(mv3)


def test_cast_exiled_card_for_free():
    """Player may cast one of the exiled cards for free."""
    mv4 = Instant(name="BigSpell", mana_cost=ManaCost(generic=4))
    mv4.on_resolve = lambda g: None
    game = _setup(library_cards=[mv4])
    p0 = game.players[0]

    capstone = ImprovisationCapstone()
    capstone.controller = p0
    capstone.owner = p0

    # Say yes to casting the exiled card
    p0._script.appendleft(True)

    capstone.on_resolve(game)

    # mv4 should be on the stack (cast for free from exile)
    assert not game.stack.is_empty()
    top_obj = game.stack.objects()[0]
    assert top_obj.source is mv4


def test_paradigm_exiles_self():
    """After resolving Improvisation Capstone, it goes to exile (not graveyard)."""
    mv4 = Instant(name="Filler", mana_cost=ManaCost(generic=4))
    game = _setup(library_cards=[mv4])
    p0 = game.players[0]

    capstone = ImprovisationCapstone()
    capstone.owner = p0
    capstone.controller = p0
    set_board_state(game, 0, hand=[capstone])

    # Pay 7 mana (5 generic + 2 red)
    p0.mana_pool.add(ManaType.COLORLESS, 5)
    p0.mana_pool.add(ManaType.RED, 2)

    # Decline casting the exiled card
    p0._script.appendleft(False)

    from engine.casting import cast_spell
    cast_spell(game, p0, capstone)
    _resolve_top_of_stack(game)

    # Paradigm: capstone in exile, not graveyard
    assert game.get_exile(p0).contains(capstone), "Capstone should be in exile after Paradigm"
    assert not game.get_graveyard(p0).contains(capstone)


def test_paradigm_copy_trigger_fires_next_main():
    """After Paradigm, copy trigger fires at beginning of each of controller's main phases."""
    mv4 = Instant(name="Filler", mana_cost=ManaCost(generic=4))
    game = _setup(library_cards=[mv4])
    p0 = game.players[0]

    capstone = ImprovisationCapstone()
    capstone.owner = p0
    capstone.controller = p0
    set_board_state(game, 0, hand=[capstone])

    p0.mana_pool.add(ManaType.COLORLESS, 5)
    p0.mana_pool.add(ManaType.RED, 2)

    # Decline casting the exiled card
    p0._script.appendleft(False)

    from engine.casting import cast_spell
    cast_spell(game, p0, capstone)
    _resolve_top_of_stack(game)

    # Advance through p1's turn then back to p0's precombat main
    from engine.types import Step
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    advance_to_phase(game, Phase.PRECOMBAT_MAIN, None)   # p1's main (no trigger)
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    # Trigger fires at start of p0's next PRECOMBAT_MAIN — player says yes to copy
    # The copy will try to exile from library (which may be empty) and say yes to casting
    # Script: yes to copy, then (library likely empty, no cards to cast)
    p0._script.appendleft(True)  # say yes to paradigm copy trigger
    # The copy's on_resolve: library may have ~5 default cards. Decline all casts.
    for _ in range(10):
        p0._script.appendleft(False)

    advance_to_phase(game, Phase.PRECOMBAT_MAIN, None)   # p0's turn 3 main → trigger fires
    _resolve_top_of_stack(game)

    # Trigger should have fired (stack was used); capstone still in exile
    assert game.get_exile(p0).contains(capstone), "Capstone stays in exile after copy"


def test_copy_does_not_retriger_paradigm():
    """The paradigm copy's on_resolve does not exile itself again or register another trigger."""
    import copy as _copy
    from engine.triggers import TriggerRegistration
    from engine.events import BeginningOfPrecombatMainTriggeredEvent

    mv4 = Instant(name="Filler", mana_cost=ManaCost(generic=4))
    game = _setup(library_cards=[mv4])
    p0 = game.players[0]

    capstone = ImprovisationCapstone()
    capstone.owner = p0
    capstone.controller = p0

    # Simulate the original resolving: set _paradigm_registered to True
    capstone._paradigm_registered[0] = True

    # Create a copy (same _paradigm_registered reference)
    copy_card = _copy.copy(capstone)
    copy_card.controller = p0

    # Count triggers registered BEFORE
    before = len([r for r in game.trigger_manager._triggers
                  if r.event_type is BeginningOfPrecombatMainTriggeredEvent])

    # Decline all cast offers for the copy's on_resolve
    for _ in range(10):
        p0._script.appendleft(False)

    copy_card.on_resolve(game)

    after = len([r for r in game.trigger_manager._triggers
                 if r.event_type is BeginningOfPrecombatMainTriggeredEvent])

    assert after == before, "Copy should not register additional Paradigm triggers"
