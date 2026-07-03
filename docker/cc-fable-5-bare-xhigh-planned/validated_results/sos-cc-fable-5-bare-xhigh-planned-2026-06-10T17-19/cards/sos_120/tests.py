"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import (
    _resolve_top_of_stack,
    advance_to_phase,
    cast_spell,
    create_game,
    set_board_state,
)


def _stock_library(player, cards):
    """Add cards bottom-to-top; the last card is the top of the library."""
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = card.controller = player
        library.add(card)


def _creature(name, cmc):
    c = Creature(name=name, base_power=1, base_toughness=1)
    c.mana_cost = ManaCost.parse(f"{{{cmc}}}")
    return c


CAPSTONE_MANA = {ManaType.COLORLESS: 5, ManaType.RED: 2}


class TestCapstoneExile:
    def test_exiles_until_total_mana_value_four(self):
        game = create_game()
        p1 = game.players[0]
        deep = _creature("Deep", 9)       # must never be exiled
        c2a = _creature("Two A", 2)
        c1 = _creature("One", 1)
        land = Land(name="Wastes")
        c2b = _creature("Two B", 2)
        # Top of library: Two B, then Wastes (MV 0), then One, then Two A.
        _stock_library(p1, [deep, c2a, c1, land, c2b])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p1._script.append(False)  # decline Two B
        p1._script.append(False)  # decline One
        p1._script.append(False)  # decline Two A
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p1)
        # 2 + 0 + 1 + 2 = 5 >= 4 → four cards exiled, Deep stays.
        for card in (c2b, land, c1, c2a):
            assert exile.contains(card)
        assert game.get_library(p1).contains(deep)

    def test_library_runs_out_before_four(self):
        game = create_game()
        p1 = game.players[0]
        only = _creature("Lonely", 1)
        _stock_library(p1, [only])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p1._script.append(False)
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(only)
        assert len(game.get_library(p1)) == 0

    def test_may_cast_exiled_spell_for_free(self):
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        bear.owner = bear.controller = p1
        flight = FleetingFlight(owner=None)
        big = _creature("Big", 3)
        # Top: Fleeting Flight (MV 1), then Big (MV 3) → total 4.
        _stock_library(p1, [big, flight])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p1._script.append(True)   # cast Fleeting Flight
        p1._script.append(bear)   # its target
        p1._script.append(False)  # decline Big
        cast_spell(game, 0, "Improvisation Capstone")
        assert bear.plus_one_counters == 1
        # The freely cast spell hits the graveyard normally; Big stays exiled.
        assert game.get_graveyard(p1).contains(flight)
        assert game.get_exile(p1).contains(big)


class TestCapstoneParadigm:
    def _resolved_capstone(self):
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=None)
        filler = _creature("Filler", 4)
        _stock_library(p1, [filler])
        set_board_state(game, 0, hand=[capstone], mana=dict(CAPSTONE_MANA))
        p1._script.append(False)  # decline casting Filler
        cast_spell(game, 0, "Improvisation Capstone")
        return game, p1, capstone

    def test_capstone_exiled_after_resolution(self):
        game, p1, capstone = self._resolved_capstone()
        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)

    def test_copy_cast_at_first_main_phase(self):
        game, p1, capstone = self._resolved_capstone()
        more = _creature("More", 5)
        _stock_library(p1, [more])
        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p2's main — no prompt
        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main
        p1._script.append(True)   # cast the paradigm copy
        p1._script.append(False)  # decline casting More from the copy
        _resolve_top_of_stack(game)
        # The copy re-ran the exile clause...
        assert game.get_exile(p1).contains(more)
        # ...the original is still in exile, and exactly one Capstone object
        # exists there (the resolved copy ceased to exist).
        exiled_capstones = [
            c for c in game.get_exile(p1).get_all()
            if getattr(c, "name", "") == "Improvisation Capstone"
        ]
        assert exiled_capstones == [capstone]
        assert not game.get_graveyard(p1).contains(capstone)

    def test_decline_keeps_offering_on_later_turns(self):
        game, p1, capstone = self._resolved_capstone()
        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p2's main
        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main
        p1._script.append(False)  # decline this turn
        _resolve_top_of_stack(game)

        more = _creature("More", 5)
        _stock_library(p1, [more])
        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p2's main
        advance_to_phase(game, Phase.ENDING, Step.END)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main again
        p1._script.append(True)
        p1._script.append(False)  # decline casting More
        _resolve_top_of_stack(game)
        assert game.get_exile(p1).contains(more)
