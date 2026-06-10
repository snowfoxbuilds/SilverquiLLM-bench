"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state, cast_spell


class _Lifer(Instant):
    def __init__(self, name="Lifer", mv=2):
        super().__init__(name=name, mana_cost=ManaCost(generic=mv))

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 10


def _lib(game, pidx, cards):
    """Place *cards* in library bottom→top (last is on top, peeled first)."""
    p = game.players[pidx]
    lib = p.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in cards:
        c.owner = p
        c.controller = p
        lib.add(c)


def _capstone_mana():
    return {ManaType.COLORLESS: 5, ManaType.RED: 2}


class TestProperties:
    def test_static(self):
        c = ImprovisationCapstone(owner=None)
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in c.subtypes


class TestMainEffect:
    def test_exile_until_mv4_and_cast(self):
        game = create_game()
        p0 = game.players[0]
        a = _Lifer("A", 2)
        b = _Lifer("B", 3)
        _lib(game, 0, [a, b])  # b on top → peeled first (3), then a (total 5)
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=_capstone_mana(), life=20)
        p0._script.extend([True, True])  # cast both
        cast_spell(game, 0, "Improvisation Capstone")
        assert p0.life == 40  # both Lifers resolved (+10 each)
        assert p0.zones[Zone.GRAVEYARD].contains(a)
        assert p0.zones[Zone.GRAVEYARD].contains(b)
        # Paradigm: Capstone itself exiled, not in graveyard.
        cap = next(c for c in p0.zones[Zone.EXILE].get_all()
                   if getattr(c, "name", "") == "Improvisation Capstone")
        assert cap is not None
        assert not any(getattr(c, "name", "") == "Improvisation Capstone"
                       for c in p0.zones[Zone.GRAVEYARD].get_all())

    def test_lands_stay_exiled(self):
        game = create_game()
        p0 = game.players[0]
        land = Land(name="A Land")
        big = _Lifer("Big", 4)
        _lib(game, 0, [big, land])  # land on top (mv0), then big (mv4)
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=_capstone_mana(), life=20)
        p0._script.extend([True])  # only the nonland prompts
        cast_spell(game, 0, "Improvisation Capstone")
        assert p0.zones[Zone.EXILE].contains(land)  # land stays exiled
        assert p0.life == 30  # big cast
        assert p0.zones[Zone.GRAVEYARD].contains(big)

    def test_library_runs_out(self):
        game = create_game()
        p0 = game.players[0]
        only = _Lifer("Only", 2)
        _lib(game, 0, [only])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=_capstone_mana(), life=20)
        p0._script.extend([True])
        cast_spell(game, 0, "Improvisation Capstone")  # must not hang
        assert p0.life == 30
        assert len(p0.zones[Zone.LIBRARY]) == 0


class TestParadigm:
    def test_recurring_copy_from_exile(self):
        game = create_game()
        p0 = game.players[0]
        a = _Lifer("A", 4)
        _lib(game, 0, [a])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=_capstone_mana(), life=20)
        p0._script.extend([True])  # cast A on first resolution
        cast_spell(game, 0, "Improvisation Capstone")
        assert p0.life == 30
        cap = next(c for c in p0.zones[Zone.EXILE].get_all()
                   if getattr(c, "name", "") == "Improvisation Capstone")

        # New fuel for the Paradigm copy.
        b = _Lifer("B", 4)
        _lib(game, 0, [b])

        # Advance to p0's next precombat main (E2 fires the Paradigm trigger).
        game.active_player_index = 0
        game.phase = Phase.BEGINNING
        game.step = Step.DRAW
        p0._script.extend([True, True])  # yes cast copy, yes cast B
        game.advance_phase()  # -> PRECOMBAT_MAIN, fires E2
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p0.life == 40  # B cast by the copy
        assert p0.zones[Zone.GRAVEYARD].contains(b)
        # Original Capstone is still in exile (a copy was cast).
        assert p0.zones[Zone.EXILE].contains(cap)
