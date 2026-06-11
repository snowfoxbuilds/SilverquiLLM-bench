"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import CastingError, cast_spell as engine_cast_spell, cast_spell_free
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _advance_to_next_precombat_main(game) -> None:
    from engine.types import Step
    from test_utils import advance_to_phase

    advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)


def _wizard() -> Creature:
    return Creature(name="Wizz", base_power=1, base_toughness=1,
                    subtypes={"Wizard"})


def _setup(p1_battlefield):
    """P2 is the active player about to cast a {2}{R} creature."""
    game = create_game(scripts=(["pass"] * 10, ["pass"] * 10))
    p1, p2 = game.players
    game.active_player_index = 1
    game.priority_player_index = 1
    game._normal_next_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None

    dragon = Creature(name="Dragon", mana_cost=ManaCost.parse("{2}{R}"),
                      base_power=4, base_toughness=4)
    set_board_state(game, 1, hand=[dragon], mana={ManaType.RED: 3})
    set_board_state(game, 0, battlefield=p1_battlefield, hand=[ManaSculpt(owner=None)],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
    engine_cast_spell(game, p2, dragon)
    return game, p1, p2, dragon


class TestManaSculpt:
    def test_counters_target_spell(self):
        game, p1, p2, dragon = _setup([])
        target = game.stack.peek()
        p1._script.appendleft(target)
        engine_cast_spell(game, p1, [c for c in p1.zones[Zone.HAND].get_all()][0])
        priority_loop(game)

        assert p2.zones[Zone.GRAVEYARD].contains(dragon)
        assert not p2.zones[Zone.BATTLEFIELD].contains(dragon)
        assert game.stack.is_empty()

    def test_wizard_grants_delayed_mana_equal_to_mana_spent(self):
        game, p1, p2, dragon = _setup([_wizard()])
        target = game.stack.peek()
        p1._script.appendleft(target)
        engine_cast_spell(game, p1, [c for c in p1.zones[Zone.HAND].get_all()][0])
        priority_loop(game)

        # Advance to P1's precombat main (crosses the turn boundary).
        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        priority_loop(game)  # resolve the delayed-mana trigger

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3  # {2}{R} = 3 paid

    def test_no_wizard_no_delayed_mana(self):
        game, p1, p2, dragon = _setup([])
        target = game.stack.peek()
        p1._script.appendleft(target)
        engine_cast_spell(game, p1, [c for c in p1.zones[Zone.HAND].get_all()][0])
        priority_loop(game)

        _advance_to_next_precombat_main(game)
        assert game.active_player is p1
        priority_loop(game)

        assert p1.mana_pool.total() == 0

    def test_countering_free_cast_gives_zero_mana(self):
        game = create_game(scripts=(["pass"] * 10, ["pass"] * 10))
        p1, p2 = game.players
        game._normal_next_index = 0
        game.active_player_index = 1
        game.priority_player_index = 1
        free_spell = Instant(name="Freebie", mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 1, hand=[free_spell])
        set_board_state(game, 0, battlefield=[_wizard()],
                        hand=[ManaSculpt(owner=None)],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        cast_spell_free(game, p2, free_spell, Zone.HAND)

        target = game.stack.peek()
        p1._script.appendleft(target)
        engine_cast_spell(game, p1, [c for c in p1.zones[Zone.HAND].get_all()][0])
        priority_loop(game)
        assert p2.zones[Zone.GRAVEYARD].contains(free_spell)

        _advance_to_next_precombat_main(game)
        priority_loop(game)
        assert p1.mana_pool.total() == 0

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=None)
        set_board_state(game, 0, hand=[sculpt],
                        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        with pytest.raises(CastingError):
            engine_cast_spell(game, p1, sculpt)
