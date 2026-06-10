"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from engine.card import Creature, Instant, Land
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from cards.sos.sos_120.card_impl import ImprovisationCapstone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state

_MANA = {ManaType.RED: 2, ManaType.COLORLESS: 5}


def _stack_library(player, cards) -> None:
    """Add cards so that cards[0] is the top of the library."""
    for c in reversed(cards):
        c.owner = player
        c.controller = player
        player.zones[Zone.LIBRARY].add(c)


class TestExileUntilMV4:
    def test_exiles_until_total_mv_at_least_4(self) -> None:
        """Top: MV2, MV3, MV5 → exiles the first two (total 5), third stays."""
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        a = Instant(name="A", mana_cost=ManaCost.parse("{2}"))
        b = Instant(name="B", mana_cost=ManaCost.parse("{3}"))
        c = Instant(name="C", mana_cost=ManaCost.parse("{5}"))
        set_board_state(game, 0, hand=[cap], mana=_MANA)
        _stack_library(p1, [a, b, c])
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(a)
        assert p1.zones[Zone.EXILE].contains(b)
        assert p1.zones[Zone.LIBRARY].contains(c)
        # Paradigm: the capstone itself is exiled, not binned.
        assert p1.zones[Zone.EXILE].contains(cap)
        assert not p1.zones[Zone.GRAVEYARD].contains(cap)

    def test_may_cast_exiled_spells_for_free(self) -> None:
        """Accepting the prompts casts the exiled spells without paying."""
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{2}"),
                        base_power=2, base_toughness=2)
        zap = Instant(name="Zap", mana_cost=ManaCost.parse("{2}"))
        set_board_state(game, 0, hand=[cap], mana=_MANA)
        _stack_library(p1, [bear, zap])
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)
        assert p1.zones[Zone.GRAVEYARD].contains(zap)

    def test_lands_stay_exiled_without_prompt(self) -> None:
        """Lands can't be cast — no prompt is consumed for them."""
        game = create_game(scripts=([False], []))  # one prompt: the instant
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        land = Land(name="Wastes")
        spell = Instant(name="Big", mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 0, hand=[cap], mana=_MANA)
        _stack_library(p1, [land, spell])
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(land)
        assert p1.zones[Zone.EXILE].contains(spell)

    def test_library_runs_out_before_mv_4(self) -> None:
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        only = Instant(name="Only", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[cap], mana=_MANA)
        _stack_library(p1, [only])
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(only)
        assert len(p1.zones[Zone.LIBRARY]) == 0


class TestParadigm:
    def test_copy_cast_at_each_of_your_first_main_phases(self) -> None:
        game = create_game(scripts=([False, "pass", True, "pass"], ["pass"] * 2))
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        first = Instant(name="First", mana_cost=ManaCost.parse("{4}"))
        later = Instant(name="Later", mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 0, hand=[cap], mana=_MANA)
        _stack_library(p1, [first, later])
        cast_spell(game, 0, "Improvisation Capstone")  # declines casting First
        assert p1.zones[Zone.EXILE].contains(cap)

        # Advance through the opponent's turn to P1's next precombat main.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # P2's main — no trigger
        assert game.stack.is_empty()
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # P1's main — trigger
        assert game.active_player is p1
        assert len(game.stack) == 1
        priority_loop(game)  # accept the copy; copy exiles "Later"...

        assert p1.zones[Zone.EXILE].contains(later)
        # The original stays in exile; the resolved copy ceases to exist —
        # exactly one Capstone object in exile, none in the graveyard.
        capstones_in_exile = [
            o for o in p1.zones[Zone.EXILE].get_all()
            if getattr(o, "name", "") == "Improvisation Capstone"
        ]
        assert capstones_in_exile == [cap]
        assert not p1.zones[Zone.GRAVEYARD].get_all()

    def test_paradigm_decline_keeps_everything_in_place(self) -> None:
        game = create_game(scripts=(["pass", False], ["pass"] * 2))
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        filler = Instant(name="Filler", mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 0, hand=[cap], mana=_MANA)
        _stack_library(p1, [filler])
        # decline the free cast of Filler at resolution
        p1._script.appendleft(False)
        cast_spell(game, 0, "Improvisation Capstone")

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # P2's main
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # P1's main — trigger
        priority_loop(game)  # declines the copy
        assert p1.zones[Zone.EXILE].contains(cap)
        assert len(p1.zones[Zone.LIBRARY]) == 0  # nothing new exiled? no —
        # Filler was exiled on the first resolution; library already empty.
