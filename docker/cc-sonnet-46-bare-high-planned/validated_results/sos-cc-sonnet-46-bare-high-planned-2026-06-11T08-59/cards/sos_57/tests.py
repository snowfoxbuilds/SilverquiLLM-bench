"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state
from test_utils import _resolve_top_of_stack


def _setup():
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    return game


def test_counters_spell():
    """Mana Sculpt counters the target spell."""
    game = _setup()
    p0, p1 = game.players

    # p1 has an instant on the stack
    target_instant = Instant(name="Fireball", mana_cost=ManaCost(generic=3))
    target_instant.on_resolve = lambda g: None
    target_instant.owner = p1
    target_instant.controller = p1
    p1.zones[Zone.STACK].add(target_instant)

    from engine.stack import StackObject
    target_so = StackObject(
        source=target_instant, controller=p1, targets=[],
        on_resolve=lambda g: None,
    )
    game.stack.push(target_so)

    sculpt = ManaSculpt()
    sculpt.owner = p0
    sculpt.controller = p0
    sculpt.chosen_targets = [target_so]
    p0.mana_pool.add(ManaType.BLUE, 2)
    p0.mana_pool.add(ManaType.COLORLESS, 1)

    sculpt.on_resolve(game)

    # target_instant should be in graveyard
    assert game.get_graveyard(p1).contains(target_instant)
    assert game.stack.is_empty()


def test_no_wizard_no_mana():
    """Without a Wizard, no delayed mana is scheduled."""
    game = _setup()
    p0, p1 = game.players

    target_instant = Instant(name="Fireball", mana_cost=ManaCost(generic=3))
    target_instant.owner = p1
    target_instant.controller = p1
    p1.zones[Zone.STACK].add(target_instant)

    from engine.stack import StackObject
    target_so = StackObject(source=target_instant, controller=p1, targets=[],
                             on_resolve=lambda g: None)
    game.stack.push(target_so)

    sculpt = ManaSculpt()
    sculpt.owner = p0
    sculpt.controller = p0
    sculpt.chosen_targets = [target_so]

    sculpt.on_resolve(game)

    # Advance to next main phase — no delayed mana trigger should fire
    advance_to_phase(game, Phase.PRECOMBAT_MAIN, None)
    _resolve_top_of_stack(game)

    assert p0.mana_pool.get(ManaType.COLORLESS) == 0


def test_wizard_triggers_delayed_mana():
    """With a Wizard, delayed {C} fires at beginning of next main phase."""
    game = _setup()
    p0, p1 = game.players

    # p0 controls a Wizard
    wizard = Creature(name="Wizard", base_power=1, base_toughness=1, subtypes={"Wizard"})
    set_board_state(game, 0, battlefield=[wizard])

    # target spell with CMC 4
    target_instant = Instant(name="Big Spell", mana_cost=ManaCost(generic=4))
    target_instant.owner = p1
    target_instant.controller = p1
    p1.zones[Zone.STACK].add(target_instant)

    from engine.stack import StackObject
    target_so = StackObject(source=target_instant, controller=p1, targets=[],
                             on_resolve=lambda g: None)
    game.stack.push(target_so)

    sculpt = ManaSculpt()
    sculpt.owner = p0
    sculpt.controller = p0
    sculpt.chosen_targets = [target_so]

    sculpt.on_resolve(game)

    # Advance through player 1's turn, then reach player 0's precombat main.
    from engine.types import Step
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)   # end of p0's turn 1
    advance_to_phase(game, Phase.PRECOMBAT_MAIN, None)   # p1's turn 2 main (no trigger)
    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)   # end of p1's turn 2
    advance_to_phase(game, Phase.PRECOMBAT_MAIN, None)   # p0's turn 3 main → trigger fires
    _resolve_top_of_stack(game)

    # Should have received 4 {C}
    assert p0.mana_pool.get(ManaType.COLORLESS) == 4


def test_can_cast_check():
    """ManaSculpt can't be cast with empty stack."""
    game = _setup()
    p0 = game.players[0]
    sculpt = ManaSculpt()
    sculpt.controller = p0
    assert not sculpt.can_cast(game)
