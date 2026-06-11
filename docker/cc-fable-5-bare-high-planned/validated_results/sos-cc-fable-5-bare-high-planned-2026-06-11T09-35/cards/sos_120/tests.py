"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.basic_lands import Plains
from engine.card import Creature, Instant, Sorcery
from engine.casting import resolve_top
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, create_game, set_board_state, cast_spell


class _LifeZap(Instant):
    """Test instant ({1}): you gain 2 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Life Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


def _fill_library(player, cards):
    """Add cards to the library bottom→top (last item ends up on top)."""
    library = player.zones[Zone.LIBRARY]
    for c in cards:
        c.owner = player
        c.controller = player
        library.add(c)


def _resolve_all(game):
    while not game.stack.is_empty():
        resolve_top(game)


class TestImprovisationCapstoneResolve:
    def test_exiles_until_mv_4_and_casts_chosen_spells(self):
        game = create_game()
        p1 = game.players[0]
        deep = Sorcery(name="Deep", mana_cost=ManaCost.parse("{1}"))
        c3 = Sorcery(name="Three Drop", mana_cost=ManaCost.parse("{3}"))
        c1 = Creature(name="One Drop", base_power=1, base_toughness=1,
                      mana_cost=ManaCost.parse("{1}"))
        zap = _LifeZap()
        # Top of library is zap, then c1, then c3, then deep.
        _fill_library(p1, [deep, c3, c1, zap])
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        # Cast prompts: cast the zap, then stop.
        p1._script.extend([zap, None])
        cast_spell(game, 0, "Improvisation Capstone")

        # zap (1) + c1 (2) + c3 (5) → stop; deep stays in the library.
        assert p1.zones[Zone.LIBRARY].contains(deep)
        exile = p1.zones[Zone.EXILE]
        assert exile.contains(c1) and exile.contains(c3)
        assert p1.life == 22, "zap was cast for free"
        assert p1.zones[Zone.GRAVEYARD].contains(zap), \
            "a non-Paradigm spell cast from exile goes to the graveyard"
        assert exile.contains(cap), "Paradigm — the Capstone exiles itself"
        assert not p1.zones[Zone.GRAVEYARD].contains(cap)

    def test_library_runs_out_below_mv_4(self):
        game = create_game()
        p1 = game.players[0]
        # Two lands (MV 0) — exile everything, never reach 4, no prompts.
        lands = [Plains(), Plains()]
        _fill_library(p1, lands)
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")

        exile = p1.zones[Zone.EXILE]
        assert all(exile.contains(land) for land in lands), \
            "uncastable lands stay exiled"
        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert exile.contains(cap)


class TestImprovisationCapstoneParadigm:
    def _resolve_capstone(self, game):
        """Cast the Capstone with an empty library (no exile prompts)."""
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")
        return cap

    def test_copy_cast_at_your_first_main_phase(self):
        game = create_game()
        p1 = game.players[0]
        cap = self._resolve_capstone(game)
        zap = _LifeZap()
        _fill_library(p1, [zap])

        # To turn 3 — P1's next precombat main (turn 2 is P2's, no fire).
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.stack.is_empty(), "no fire on opponent's main phase"
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        p1._script.extend([True, zap])  # cast the copy; cast exiled zap
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        _resolve_all(game)

        assert p1.life == 22, "the copy exiled and cast the zap"
        assert p1.zones[Zone.EXILE].contains(cap), \
            "the physical card never leaves exile"
        assert p1.zones[Zone.GRAVEYARD].contains(zap)

    def test_recurring_every_first_main_and_declinable(self):
        game = create_game()
        p1 = game.players[0]
        cap = self._resolve_capstone(game)

        # Turn 3: decline.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        p1._script.append(False)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_all(game)
        assert p1.life == 20

        # Turn 5: accept (empty library — copy resolves, exiles nothing).
        for _ in range(2):
            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        p1._script.append(True)
        _resolve_all(game)
        assert p1.zones[Zone.EXILE].contains(cap)
        assert len(game.trigger_manager.get_triggers_for_source(cap)) == 1, \
            "the Paradigm trigger recurs — it is never consumed"

    def test_second_capstone_resolution_does_not_double_register(self):
        game = create_game()
        p1 = game.players[0]
        cap1 = self._resolve_capstone(game)
        cap2 = ImprovisationCapstone(owner=None)
        set_board_state(game, 0, hand=[cap2],
                        mana={ManaType.RED: 2, ManaType.COLORLESS: 5})
        cast_spell(game, 0, "Improvisation Capstone")

        triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.source in (cap1, cap2)
        ]
        assert len(triggers) == 1, "only the first resolution registers"
        assert p1.zones[Zone.EXILE].contains(cap2), \
            "the second copy still exiles itself"
