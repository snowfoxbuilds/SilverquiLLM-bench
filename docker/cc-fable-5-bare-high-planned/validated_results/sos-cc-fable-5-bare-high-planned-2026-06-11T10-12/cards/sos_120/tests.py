"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.basic_lands import Plains
from engine.card import Instant
from engine.casting import resolve_top
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, create_game, cast_spell, set_board_state

CAST_MANA = {ManaType.RED: 2, ManaType.COLORLESS: 5}


def _filler(name, mv):
    return Instant(name=name, mana_cost=ManaCost.parse(f"{{{mv}}}"))


class Probe(Instant):
    """Test-local instant: controller gains 3 life. Mana value 4."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Probe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 3


def _stock_library(player, cards):
    """Add cards bottom-first; the last item ends up on top."""
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestResolution:
    def test_exiles_until_total_mana_value_four(self):
        """Top cards {2} + {2} reach MV 4; deeper cards stay in library."""
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1)
        set_board_state(game, 0, hand=[cap], mana=CAST_MANA)
        _stock_library(p1, [_filler("F0", 1), _filler("F1", 1),
                            _filler("F2", 2), _filler("F3", 2)])
        p1._script.extend([False, False])  # decline both free casts
        cast_spell(game, 0, "Improvisation Capstone")

        exile = p1.zones[Zone.EXILE]
        assert len(exile) == 3  # F3, F2 and the Capstone itself
        assert exile.contains(cap)
        assert len(p1.zones[Zone.LIBRARY]) == 2
        assert len(p1.zones[Zone.GRAVEYARD]) == 0  # Paradigm: exiled, not binned

    def test_free_cast_from_among_exiled(self):
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1)
        probe = Probe(owner=p1)
        set_board_state(game, 0, hand=[cap], mana=CAST_MANA)
        _stock_library(p1, [probe])
        p1._script.append(True)  # cast the exiled Probe for free
        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.life == 23
        assert p1.zones[Zone.GRAVEYARD].contains(probe)
        assert p1.zones[Zone.EXILE].contains(cap)

    def test_library_runs_out_before_mv_four(self):
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1)
        set_board_state(game, 0, hand=[cap], mana=CAST_MANA)
        _stock_library(p1, [_filler("F0", 1)])
        p1._script.append(False)
        cast_spell(game, 0, "Improvisation Capstone")

        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert len(p1.zones[Zone.EXILE]) == 2  # F0 + Capstone

    def test_lands_stay_exiled_without_prompt(self):
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1)
        plains = Plains(owner=p1)
        probe = Probe(owner=p1)
        set_board_state(game, 0, hand=[cap], mana=CAST_MANA)
        _stock_library(p1, [probe, plains])  # plains on top (MV 0)
        p1._script.append(False)  # single prompt: for Probe only
        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(plains)
        assert p1.zones[Zone.EXILE].contains(probe)
        assert len(p1._script) == 0


class TestParadigm:
    def test_copy_cast_each_of_your_first_main_phases(self):
        game = create_game()
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=p1)
        set_board_state(game, 0, hand=[cap], mana=CAST_MANA)
        _stock_library(p1, [Probe(owner=p1), _filler("Top", 4)])
        p1._script.append(False)  # decline the free cast of "Top"
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(cap)

        # Turn 2 is the opponent's — no trigger fires for p1.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
        assert game.stack.is_empty()

        # Turn 3: p1's first main phase — may cast a copy from exile.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        assert len(game.stack) == 1
        p1._script.extend([True, True])  # cast the copy; free-cast Probe
        resolve_top(game)  # the paradigm trigger → pushes the copy
        resolve_top(game)  # the copy resolves → exiles Probe, casts it
        resolve_top(game)  # Probe resolves

        assert p1.life == 23
        # Capstone itself is still (only once) in exile.
        assert sum(1 for c in p1.zones[Zone.EXILE].get_all() if c is cap) == 1
        assert len(p1.zones[Zone.LIBRARY]) == 0

    def test_recurs_on_following_turns(self):
        game = create_game()
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=p1)
        set_board_state(game, 0, hand=[cap], mana=CAST_MANA)
        cast_spell(game, 0, "Improvisation Capstone")  # empty library: no prompts

        for _ in range(2):  # two of p1's turns in a row
            advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # opponent's main
            advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # p1's main
            assert len(game.stack) == 1
            p1._script.append(False)  # decline the copy
            resolve_top(game)
            assert game.stack.is_empty()
