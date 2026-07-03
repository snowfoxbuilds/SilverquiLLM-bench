"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.basic_lands import Mountain
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


def _stock_library(game, player_index, cards):
    """Place *cards* into the library, first element = bottom, last = top."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for c in cards:
        c.owner = player
        c.controller = player
        library.add(c)


def _mana7():
    return {ManaType.RED: 2, ManaType.COLORLESS: 5}


class TestImprovisationCapstone:
    def test_exiles_until_mv_4_and_casts_for_free(self):
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=None)
        small = Creature(name="Small", mana_cost=ManaCost.parse("{1}"),
                         base_power=1, base_toughness=1)
        big = Creature(name="Big", mana_cost=ManaCost.parse("{3}"),
                       base_power=3, base_toughness=3)
        deep = Creature(name="Deep", mana_cost=ManaCost.parse("{2}"),
                        base_power=2, base_toughness=2)
        # Top of library = last added: order from top is small (1), big (3).
        set_board_state(game, 0, hand=[cap], mana=_mana7())
        _stock_library(game, 0, [deep, big, small])

        # Cast both exiled spells for free.
        p1._script.extend([True, True])
        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.BATTLEFIELD].contains(small)
        assert p1.zones[Zone.BATTLEFIELD].contains(big)
        assert p1.zones[Zone.LIBRARY].contains(deep)   # stopped at MV 4
        assert p1.zones[Zone.EXILE].contains(cap)      # Paradigm exile

    def test_library_runs_out_before_mv_4(self):
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=None)
        only = Creature(name="Only", mana_cost=ManaCost.parse("{1}"),
                        base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[cap], mana=_mana7())
        _stock_library(game, 0, [only])

        p1._script.extend([False])  # decline casting it
        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(only)
        assert p1.zones[Zone.EXILE].contains(cap)
        assert len(p1.zones[Zone.LIBRARY]) == 0

    def test_lands_stay_exiled_without_prompt(self):
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=None)
        land = Mountain()
        big = Creature(name="Big", mana_cost=ManaCost.parse("{4}"),
                       base_power=4, base_toughness=4)
        set_board_state(game, 0, hand=[cap], mana=_mana7())
        _stock_library(game, 0, [big, land])  # top: land (MV 0), then big

        p1._script.extend([True])  # single prompt: cast Big
        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(land)
        assert p1.zones[Zone.BATTLEFIELD].contains(big)
        assert p1.remaining_choices == 0  # no prompt was consumed for the land

    def test_paradigm_copy_each_of_your_first_main_phases(self):
        game = create_game(scripts=(["pass"] * 40, ["pass"] * 40))
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=None)
        l1, l2 = Mountain(), Mountain()
        set_board_state(game, 0, hand=[cap], mana=_mana7())
        _stock_library(game, 0, [l2, l1])

        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(cap)
        assert p1.zones[Zone.EXILE].contains(l1)   # MV 0, library continues
        assert p1.zones[Zone.EXILE].contains(l2)   # library ran out

        # Refill library so the copy has something to exile.
        c1 = Creature(name="C1", mana_cost=ManaCost.parse("{5}"),
                      base_power=5, base_toughness=5)
        _stock_library(game, 0, [c1])

        # Opponent's main phase: no trigger for us.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
        assert game.stack.is_empty()

        # Our next precombat main: may cast a copy from exile.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        assert len(game.stack) == 1  # the Paradigm trigger

        # Prompt order: pass, [trigger: copy? yes], pass,
        # [copy resolution: cast C1? yes], then passes to drain the stack.
        from collections import deque
        p1._script = deque(["pass", True, "pass", True] + ["pass"] * 6)
        priority_loop(game)

        assert p1.zones[Zone.BATTLEFIELD].contains(c1)
        assert p1.zones[Zone.EXILE].contains(cap)  # original stays exiled
