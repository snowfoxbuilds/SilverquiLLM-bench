"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, create_game, set_board_state, _resolve_top_of_stack


class SimpleInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "TargetInstant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


class WizardCreature(Creature):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Wizard")
        kwargs.setdefault("subtypes", {"Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)


def _advance_to_next_precombat_main(game, target_player):
    """Advance phase until we hit PRECOMBAT_MAIN with target_player as active."""
    from engine.game_state import _TURN_SEQUENCE
    orig_turn = game.turn_number
    for _ in range(len(_TURN_SEQUENCE) * 3):
        game.advance_phase()
        if (game.phase == Phase.PRECOMBAT_MAIN and
                game.active_player is target_player and
                game.turn_number > orig_turn):
            return
    raise RuntimeError("Could not advance to next precombat main phase")


def test_counters_target_spell():
    """Mana Sculpt counters the target spell."""
    from engine.casting import cast_spell as _cast
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    sculpt = ManaSculpt()
    target = SimpleInstant()

    set_board_state(game, 1, hand=[target])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 1
    p2.mana_pool.add(ManaType.BLUE, 1)
    p2.mana_pool.add(ManaType.COLORLESS, 2)
    _cast(game, p2, target)

    # p1 counters with sculpt
    set_board_state(game, 0, hand=[sculpt])
    p1.mana_pool.add(ManaType.BLUE, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(game.stack.peek())  # target = the instant on stack

    _cast(game, p1, sculpt)
    _resolve_top_of_stack(game)

    assert target in game.get_graveyard(p2).get_all()


def test_no_mana_if_no_wizard():
    """No delayed mana when controller doesn't control a Wizard."""
    from engine.casting import cast_spell as _cast
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    sculpt = ManaSculpt()
    target = SimpleInstant()

    set_board_state(game, 1, hand=[target])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 1
    p2.mana_pool.add(ManaType.BLUE, 1)
    p2.mana_pool.add(ManaType.COLORLESS, 2)
    _cast(game, p2, target)

    set_board_state(game, 0, hand=[sculpt])
    p1.mana_pool.add(ManaType.BLUE, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(game.stack.peek())

    _cast(game, p1, sculpt)
    _resolve_top_of_stack(game)

    _advance_to_next_precombat_main(game, p1)
    _resolve_top_of_stack(game)

    assert p1.mana_pool.get(ManaType.COLORLESS) == 0


def test_mana_added_on_next_main_phase_with_wizard():
    """With a Wizard, add {C} equal to countered spell's mana value at next main phase."""
    from engine.casting import cast_spell as _cast
    from engine.player import DeterministicPlayer

    game = create_game()
    p1 = game.players[0]
    p2 = game.players[1]

    sculpt = ManaSculpt()
    target = SimpleInstant()  # mana cost {2}{U} = MV 3
    wizard = WizardCreature()

    set_board_state(game, 1, hand=[target])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    game.active_player_index = 1
    p2.mana_pool.add(ManaType.BLUE, 1)
    p2.mana_pool.add(ManaType.COLORLESS, 2)
    _cast(game, p2, target)

    set_board_state(game, 0, hand=[sculpt], battlefield=[wizard])
    p1.mana_pool.add(ManaType.BLUE, 2)
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    if isinstance(p1, DeterministicPlayer):
        p1._script.appendleft(game.stack.peek())

    _cast(game, p1, sculpt)
    _resolve_top_of_stack(game)

    # Advance to the NEXT turn's precombat main phase for p1
    _advance_to_next_precombat_main(game, p1)
    _resolve_top_of_stack(game)

    # {2}{U} = 3 mana → 3 colorless added
    assert p1.mana_pool.get(ManaType.COLORLESS) == 3
