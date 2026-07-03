"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land, Sorcery
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state, cast_spell, advance_to_phase


class LifeGain(Instant):
    """Free-castable test spell: gain 3 life on resolve."""

    def __init__(self, mv=2, **kwargs: Any) -> None:
        kwargs.setdefault("name", f"LifeGain{mv}")
        kwargs.setdefault("mana_cost", ManaCost.parse("{%d}" % mv))
        super().__init__(**kwargs)

    def on_resolve(self, game) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _set_library(game, player_index, cards):
    """Place *cards* in library bottom→top (last item is the top)."""
    player = game.players[player_index]
    lib = player.zones[Zone.LIBRARY]
    for obj in lib.get_all():
        lib.remove(obj)
    for c in cards:
        c.owner = player
        c.controller = player
        lib.add(c)


class TestProperties:
    def test_static(self):
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes


class TestMainEffect:
    def test_exiles_until_mv_four(self):
        game = create_game()
        p1 = game.players[0]
        # top→ s2(2), s1(2), deep(2). Peel s2(2), s1(4>=4 stop).
        deep, s1, s2 = LifeGain(2, name="Deep"), LifeGain(2, name="S1"), LifeGain(2, name="S2")
        _set_library(game, 0, [deep, s1, s2])
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p1._script.extend([False, False])  # decline casting both exiled spells
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p1)
        assert exile.contains(s2) and exile.contains(s1)
        assert not exile.contains(deep)  # stopped at MV 4
        assert game.get_library(p1).contains(deep)

    def test_may_cast_exiled_spells_free(self):
        game = create_game()
        p1 = game.players[0]
        s1, s2 = LifeGain(2, name="S1"), LifeGain(2, name="S2")
        _set_library(game, 0, [s1, s2])
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap], life=20,
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p1._script.extend([True, True])  # cast both
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.life == 26  # +3 each
        # Cast spells go to graveyard (resolved); not still in exile.
        assert game.get_graveyard(p1).contains(s1)
        assert game.get_graveyard(p1).contains(s2)

    def test_lands_stay_exiled(self):
        game = create_game()
        p1 = game.players[0]
        # land has MV 0, so it never satisfies MV>=4 on its own; pair with a spell.
        land = Land(name="ExiledLand")
        big = LifeGain(4, name="Big4")  # MV 4 top
        _set_library(game, 0, [land, big])
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap], mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p1._script.extend([False])  # decline casting the spell (land not prompted)
        cast_spell(game, 0, "Improvisation Capstone")
        # Big4 reached MV 4 → only it exiled; land stays in library.
        assert game.get_exile(p1).contains(big)
        assert game.get_library(p1).contains(land)

    def test_library_runs_out(self):
        game = create_game()
        p1 = game.players[0]
        only = LifeGain(2, name="Only")
        _set_library(game, 0, [only])
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap], mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p1._script.extend([False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(only)
        assert len(game.get_library(p1).get_all()) == 0


class TestParadigm:
    def test_capstone_exiled_after_resolving(self):
        game = create_game()
        p1 = game.players[0]
        s = LifeGain(4, name="Quad")
        _set_library(game, 0, [s])
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap], mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p1._script.extend([False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(cap)
        assert not game.get_graveyard(p1).contains(cap)

    def test_recurring_copy_next_main_phase(self):
        game = create_game()
        p1 = game.players[0]
        # Library: bottom forCopy(4), top first(4). First cast exiles `first`,
        # leaving `forCopy` for the recurring copy next main phase.
        for_copy = LifeGain(4, name="ForCopy")
        first = LifeGain(4, name="First")
        _set_library(game, 0, [for_copy, first])
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap], mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        p1._script.extend([False])  # don't cast `first`
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p1).contains(cap)
        assert game.get_exile(p1).contains(first)
        assert game.get_library(p1).contains(for_copy)

        # Advance to p1's next precombat main; recurring copy fires.
        game.active_player_index = 0
        game.turn_number = 3
        game.phase = Phase.BEGINNING
        game.step = Step.UPKEEP
        # script: yes (cast copy), then no (don't cast `for_copy` once exiled)
        p1._script.extend([True, False])
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        # resolve trigger → copy → copy's main effect
        from engine.state_based_actions import resolve_state_based_actions
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
            resolve_state_based_actions(game)
        # The copy re-ran the main effect: for_copy now exiled.
        assert game.get_exile(p1).contains(for_copy)
        # Original Capstone still in exile (copy doesn't move it).
        assert game.get_exile(p1).contains(cap)
