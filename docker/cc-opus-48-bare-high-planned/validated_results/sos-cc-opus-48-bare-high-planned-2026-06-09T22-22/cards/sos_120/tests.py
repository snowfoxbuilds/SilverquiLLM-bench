"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land, Sorcery
from engine.state_based_actions import resolve_state_based_actions
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state, cast_spell


def _creature(name, cost):
    return Creature(name=name, base_power=1, base_toughness=1,
                    mana_cost=ManaCost.parse(cost))


def _stock_library(game, player_index, cards_bottom_to_top):
    p = game.players[player_index]
    lib = game.get_library(p)
    for c in cards_bottom_to_top:
        c.owner = p
        c.controller = p
        lib.add(c)  # appends → last added is on top


def _advance_to_my_next_precombat_main(game, player):
    for _ in range(40):
        game.advance_phase()
        if (game.phase is Phase.PRECOMBAT_MAIN and game.active_player is player
                and game.turn_number > 1):
            return
    raise AssertionError("did not reach player's next precombat main")


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _names(zone):
    return [getattr(c, "name", "?") for c in zone.get_all()]


class TestProperties:
    def test_basics(self):
        c = ImprovisationCapstone(owner=None)
        assert isinstance(c, Sorcery)
        assert c.name == "Improvisation Capstone"
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in c.subtypes


class TestImprovise:
    def test_exiles_until_mv4_and_casts(self):
        game = create_game(scripts=([True, True], []))
        p0 = game.players[0]
        # Top of library (peeled first) = "Three" (mv3), then "Two" (mv2).
        _stock_library(game, 0, [_creature("Two", "{1}{R}"), _creature("Three", "{2}{R}")])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        bf = _names(game.get_battlefield(p0))
        assert "Three" in bf and "Two" in bf
        # Capstone exiled itself (Paradigm), not in graveyard.
        assert "Improvisation Capstone" in _names(game.get_exile(p0))
        assert "Improvisation Capstone" not in _names(game.get_graveyard(p0))

    def test_lands_stay_exiled(self):
        game = create_game(scripts=([True], []))
        p0 = game.players[0]
        land = Land(name="Waste")
        # Top = land (mv0), then creature mv4 → total 4, stop.
        _stock_library(game, 0, [_creature("Big", "{3}{R}"), land])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        assert "Big" in _names(game.get_battlefield(p0))
        # Land cannot be cast — remains in exile, never on the battlefield.
        assert "Waste" in _names(game.get_exile(p0))
        assert "Waste" not in _names(game.get_battlefield(p0))

    def test_library_runs_out(self):
        game = create_game(scripts=([True], []))
        p0 = game.players[0]
        _stock_library(game, 0, [_creature("Lonely", "{1}{R}")])  # mv2 only
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        assert "Lonely" in _names(game.get_battlefield(p0))
        assert len(game.get_library(p0)) == 0


class TestParadigm:
    def test_recurring_copy_next_main(self):
        # First cast scripts [True, True]; the Paradigm copy next turn scripts
        # [True (cast copy), True (cast the newly exiled creature)].
        game = create_game(scripts=([True, True, True, True], []))
        p0 = game.players[0]
        _stock_library(game, 0, [
            _creature("Para", "{3}{R}"),   # bottom (mv4) — exiled next turn
            _creature("Two", "{1}{R}"),
            _creature("Three", "{2}{R}"),  # top
        ])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        cast_spell(game, 0, "Improvisation Capstone")
        assert "Para" not in _names(game.get_battlefield(p0))  # not yet

        _advance_to_my_next_precombat_main(game, p0)
        _drain(game)
        # The copy resolved its improvisation, exiling & casting "Para".
        assert "Para" in _names(game.get_battlefield(p0))
        # Original Capstone is still in exile (copy, not the original, was cast).
        assert "Improvisation Capstone" in _names(game.get_exile(p0))
