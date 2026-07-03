"""Tests for The Dawning Archaic (sos_1)."""

from __future__ import annotations

import pytest

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, declare_attackers, set_board_state


def _game_with_archaic(graveyard_spells=None):
    """Set up a game with Archaic on battlefield and optional graveyard spells."""
    archaic = TheDawningArchaic()
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    p0 = game.players[0]

    from engine.zones import move_to_zone
    archaic.owner = p0
    archaic.controller = p0
    archaic.summoning_sick = False
    game.get_battlefield(p0).add(archaic)
    archaic.register_triggers(game)

    if graveyard_spells:
        for spell in graveyard_spells:
            spell.owner = p0
            spell.controller = p0
            game.get_graveyard(p0).add(spell)

    return game, archaic


def test_cost_reduction_two_instants():
    """Costs {2} less with two instants in graveyard."""
    i1 = Instant(name="Bolt")
    i2 = Instant(name="Counterspell")
    game, archaic = _game_with_archaic(graveyard_spells=[i1, i2])
    p0 = game.players[0]
    archaic.controller = p0
    assert archaic.cost_reduction(game) == 2


def test_cost_reduction_empty_graveyard():
    """No reduction with empty graveyard."""
    game, archaic = _game_with_archaic()
    p0 = game.players[0]
    archaic.controller = p0
    assert archaic.cost_reduction(game) == 0


def test_cost_reduction_ignores_creatures():
    """Only instants/sorceries count for cost reduction."""
    creature = Creature(name="Bear", base_power=2, base_toughness=2)
    s1 = Sorcery(name="Wrath")
    game, archaic = _game_with_archaic(graveyard_spells=[creature, s1])
    p0 = game.players[0]
    archaic.controller = p0
    # Only sorcery counts
    assert archaic.cost_reduction(game) == 1


def test_attack_trigger_casts_from_graveyard():
    """Attack trigger allows casting instant from graveyard; spell goes to exile."""
    instant = Instant(name="Lightning Bolt", mana_cost=ManaCost(generic=1))
    instant.on_resolve = lambda g: None  # harmless effect

    game, archaic = _game_with_archaic(graveyard_spells=[instant])
    p0 = game.players[0]
    p1 = game.players[1]

    # Script: yes to cast, then the instant needs no targets
    p0._script.appendleft(True)   # choose_yes_no: yes, cast it

    # Simulate the attack trigger firing
    from engine.events import AttacksTriggeredEvent
    event = AttacksTriggeredEvent(creature=archaic)
    game.trigger_manager.fire_event(game, event)

    # Resolve the trigger from the stack
    from test_utils import _resolve_top_of_stack
    _resolve_top_of_stack(game)

    # Instant should have been cast (moved from graveyard), and replacement
    # should have sent it to exile (not graveyard).
    exile = game.get_exile(p0)
    graveyard = game.get_graveyard(p0)
    assert exile.contains(instant), "Spell should be exiled, not in graveyard"
    assert not graveyard.contains(instant)


def test_attack_trigger_empty_graveyard_does_nothing():
    """Attack trigger with empty graveyard does nothing."""
    game, archaic = _game_with_archaic()
    p0 = game.players[0]

    from engine.events import AttacksTriggeredEvent
    event = AttacksTriggeredEvent(creature=archaic)
    game.trigger_manager.fire_event(game, event)

    from test_utils import _resolve_top_of_stack
    _resolve_top_of_stack(game)  # Should not raise or crash

    assert game.stack.is_empty()


def test_reach_keyword():
    """The Dawning Archaic has Reach."""
    archaic = TheDawningArchaic()
    assert Keyword.REACH in archaic.keywords
