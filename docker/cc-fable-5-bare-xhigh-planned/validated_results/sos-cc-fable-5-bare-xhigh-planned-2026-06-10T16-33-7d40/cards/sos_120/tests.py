"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Sorcery
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state

CAPSTONE_MANA = {ManaType.RED: 2, ManaType.COLORLESS: 5}


class GainOne(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gain One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


def _stack_library(game, player_index, cards) -> None:
    """Put *cards* into the library; the LAST item ends up on top."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestImprovisationCapstoneProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in card.subtypes


class TestExileUntilFour:
    def test_exiles_until_total_mv_four_then_stops(self) -> None:
        game = create_game()
        filler = Instant(name="Filler", mana_cost=ManaCost.parse("{1}"))
        c3 = Creature(name="TwoDrop", base_power=2, base_toughness=2,
                      mana_cost=ManaCost.parse("{1}{G}"))   # MV 2
        c2 = Instant(name="OneA", mana_cost=ManaCost.parse("{W}"))  # MV 1
        c1 = Instant(name="OneB", mana_cost=ManaCost.parse("{U}"))  # MV 1
        # Library bottom -> top: filler, c3, c2, c1 (c1 on top).
        _stack_library(game, 0, [filler, c3, c2, c1])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p0 = game.players[0]
        # Decline all three castable spells.
        p0._script.extend([False, False, False])

        cast_spell(game, 0, "Improvisation Capstone")

        exile_names = {c.name for c in p0.zones[Zone.EXILE].get_all()}
        # 1 + 1 + 2 = 4 -> stop; filler stays in the library.
        assert {"OneB", "OneA", "TwoDrop"} <= exile_names
        assert [c.name for c in p0.zones[Zone.LIBRARY].get_all()] == ["Filler"]
        # Paradigm: the Capstone itself is exiled, not binned.
        assert "Improvisation Capstone" in exile_names
        assert len(p0.zones[Zone.GRAVEYARD]) == 0

    def test_library_runs_out_before_four(self) -> None:
        game = create_game()
        only = Instant(name="Only", mana_cost=ManaCost.parse("{U}"))
        _stack_library(game, 0, [only])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p0 = game.players[0]
        p0._script.extend([False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert len(p0.zones[Zone.LIBRARY]) == 0
        assert only in p0.zones[Zone.EXILE].get_all()


class TestFreeCasts:
    def test_may_cast_exiled_spells_for_free(self) -> None:
        game = create_game()
        gain = GainOne()
        big = Creature(name="Big", base_power=4, base_toughness=4,
                       mana_cost=ManaCost.parse("{3}{G}"))  # MV 4
        # top: gain (MV 1), then big (MV 4) -> total 5, stop.
        _stack_library(game, 0, [big, gain])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p0 = game.players[0]
        # Cast Gain One (yes), decline Big.
        p0._script.extend([True, False])

        cast_spell(game, 0, "Improvisation Capstone")

        assert p0.life == 21
        assert gain in p0.zones[Zone.GRAVEYARD].get_all()
        assert big in p0.zones[Zone.EXILE].get_all()

    def test_lands_stay_exiled_and_are_not_offered(self) -> None:
        from engine.basic_lands import Mountain

        game = create_game()
        land = Mountain()
        big = Creature(name="Big", base_power=4, base_toughness=4,
                       mana_cost=ManaCost.parse("{3}{G}"))
        _stack_library(game, 0, [big, land])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p0 = game.players[0]
        # Only one yes/no prompt should occur (for Big).
        p0._script.extend([False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert land in p0.zones[Zone.EXILE].get_all()
        assert len(p0._script) == 0


class TestParadigm:
    def test_recast_each_of_your_first_main_phases(self) -> None:
        game = create_game()
        gain_a, gain_b = GainOne(), GainOne()
        _stack_library(game, 0, [gain_b, gain_a])
        set_board_state(game, 0, hand=[ImprovisationCapstone(owner=None)],
                        mana=dict(CAPSTONE_MANA))
        p0, p1 = game.players
        # First resolution exiles both GainOnes (1+1 = 2 < 4, library out);
        # decline both.
        p0._script.extend([False, False])
        cast_spell(game, 0, "Improvisation Capstone")
        capstone = next(
            c for c in p0.zones[Zone.EXILE].get_all()
            if c.name == "Improvisation Capstone"
        )

        # Advance to P0's next precombat main (turn 3).
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p1
        priority_loop(game)  # no trigger for p1's main
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p0
        # Trigger on stack: pass, yes to recast, then both exiled GainOnes
        # were declined on the first pass... library is empty now, so the
        # recast exiles nothing and offers nothing.
        p0._script.extend(["pass", True, "pass"])
        p1._script.extend(["pass", "pass"])
        priority_loop(game)

        # Capstone is back in exile after the recast resolution.
        assert capstone in p0.zones[Zone.EXILE].get_all()
        assert capstone not in p0.zones[Zone.GRAVEYARD].get_all()

        # And it fires again on P0's NEXT turn too (recurring).
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        priority_loop(game)  # p1's main: nothing
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p0
        p0._script.extend(["pass", False])
        p1._script.extend(["pass"])
        priority_loop(game)
        assert capstone in p0.zones[Zone.EXILE].get_all()
