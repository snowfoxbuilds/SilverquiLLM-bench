"""Tests for Improvisation Capstone (sos_120)."""

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.basic_lands import Mountain
from engine.card import Instant
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state, cast_spell


class LifeGainInstant(Instant):
    def __init__(self, name="LG", cost="{2}", **kw):
        kw.setdefault("mana_cost", ManaCost.parse(cost))
        super().__init__(name=name, **kw)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


def _stack_library(game, player_index, cards):
    """Place *cards* in the library, last item = top."""
    lib = game.players[player_index].zones[Zone.LIBRARY]
    for c in cards:
        c.owner = game.players[player_index]
        c.controller = game.players[player_index]
        lib.add(c)


class TestImprovisationCapstone:
    def test_exiles_until_total_mv_four(self):
        game = create_game()
        p0 = game.players[0]
        deep = LifeGainInstant("Deep", "{5}")     # should never be exiled
        c3 = LifeGainInstant("C3", "{3}")
        c1 = LifeGainInstant("C1", "{1}")
        c2 = LifeGainInstant("C2", "{2}")
        _stack_library(game, 0, [deep, c3, c1, c2])  # top: c2, then c1, c3
        set_board_state(game, 0, hand=[ImprovisationCapstone()],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        # decline all three casts (2+1+3 = 6 >= 4 after third card)
        p0._script.extend([False, False, False])
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p0)
        assert exile.contains(c2) and exile.contains(c1) and exile.contains(c3)
        assert not exile.contains(deep)
        assert len(game.get_library(p0)) == 1

    def test_free_casts_resolve(self):
        game = create_game()
        p0 = game.players[0]
        a = LifeGainInstant("A", "{2}")
        b = LifeGainInstant("B", "{2}")
        _stack_library(game, 0, [a, b])
        set_board_state(game, 0, hand=[ImprovisationCapstone()],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        p0._script.extend([True, True])
        cast_spell(game, 0, "Improvisation Capstone")
        assert p0.life == 22  # both free spells resolved

    def test_library_runs_out(self):
        game = create_game()
        p0 = game.players[0]
        only = LifeGainInstant("Only", "{1}")
        _stack_library(game, 0, [only])
        set_board_state(game, 0, hand=[ImprovisationCapstone()],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        p0._script.extend([False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p0).contains(only)
        assert len(game.get_library(p0)) == 0

    def test_lands_stay_exiled_uncastable(self):
        game = create_game()
        p0 = game.players[0]
        m1, m2 = Mountain(name="Mountain"), Mountain(name="Mountain")
        big = LifeGainInstant("Big", "{4}")
        _stack_library(game, 0, [big, m1, m2])  # top: m2, m1, big (0+0+4)
        set_board_state(game, 0, hand=[ImprovisationCapstone()],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        p0._script.extend([False])  # only Big prompts; lands never do
        cast_spell(game, 0, "Improvisation Capstone")
        exile = game.get_exile(p0)
        assert exile.contains(m1) and exile.contains(m2) and exile.contains(big)

    def test_paradigm_exiles_itself_and_recurs(self):
        game = create_game()
        p0, p1 = game.players
        cards = [LifeGainInstant(f"L{i}", "{4}") for i in range(3)]
        _stack_library(game, 0, cards)
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        p0._script.append(False)  # decline cast of first exiled card
        cast_spell(game, 0, "Improvisation Capstone")
        assert game.get_exile(p0).contains(cap)
        assert not game.get_graveyard(p0).contains(cap)
        assert len([c for c in game.get_exile(p0).get_all()
                    if c.name.startswith("L")]) == 1

        # Advance to p0's next precombat main: trigger offers a copy.
        for _ in range(40):
            game.advance_phase()
            if game.phase is Phase.PRECOMBAT_MAIN and game.active_player is p0:
                break
        # Priority script: pass, (trigger resolves -> yes to copy), pass,
        # (copy resolves -> decline casting newly exiled card), final passes.
        p0._script.extend(["pass", True, "pass", False, "pass"])
        p1._script.extend(["pass", "pass", "pass"])
        priority_loop(game)
        assert game.get_exile(p0).contains(cap)   # card stays in exile
        # The copy's effect ran: another library card was exiled.
        exiled_ls = [c for c in game.get_exile(p0).get_all() if c.name.startswith("L")]
        assert len(exiled_ls) == 2
