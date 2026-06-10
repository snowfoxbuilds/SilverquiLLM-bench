"""Tests for SOS 120 — Improvisation Capstone (Paradigm)."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _creature(name: str, mv: int) -> Creature:
    return Creature(name=name, base_power=1, base_toughness=1,
                    mana_cost=ManaCost.parse(f"{{{mv}}}"))


def _stack_library(player, cards) -> None:
    """Put *cards* into the library; the LAST item ends up on top."""
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = card.controller = player
        library.add(card)


def _cast_capstone(game, extra_script=None):
    p1 = game.players[0]
    capstone = ImprovisationCapstone()
    set_board_state(
        game, 0, hand=[capstone],
        mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
    )
    if extra_script:
        p1._script.extend(extra_script)
    cast_spell(game, 0, "Improvisation Capstone")
    return capstone


class TestProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone()
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in card.subtypes


class TestExileUntilMV4:
    def test_exiles_until_total_mv_4_and_self_exiles(self) -> None:
        """Tops {1},{2},{3}: 1+2 < 4, +3 → 3 cards exiled; Capstone exiled too."""
        game = create_game()
        p1 = game.players[0]
        a, b, c, deep = _creature("A", 3), _creature("B", 2), _creature("C", 1), _creature("Deep", 5)
        _stack_library(p1, [deep, a, b, c])  # top order: C, B, A, Deep

        capstone = _cast_capstone(game, extra_script=[None])  # decline all casts

        exile = p1.zones[Zone.EXILE]
        assert exile.contains(c) and exile.contains(b) and exile.contains(a)
        assert p1.zones[Zone.LIBRARY].contains(deep)
        assert exile.contains(capstone)  # Paradigm: exiled, not graveyard
        assert not p1.zones[Zone.GRAVEYARD].contains(capstone)

    def test_library_runs_out_before_mv_4(self) -> None:
        game = create_game()
        p1 = game.players[0]
        only = _creature("Only", 2)
        _stack_library(p1, [only])

        _cast_capstone(game, extra_script=[None])

        assert p1.zones[Zone.EXILE].contains(only)
        assert len(p1.zones[Zone.LIBRARY]) == 0

    def test_may_cast_some_lands_stay_exiled(self) -> None:
        """Cast one exiled creature; the land is never a candidate."""
        game = create_game()
        p1 = game.players[0]
        wolf = _creature("Wolf", 4)
        land = Land(name="Wastes")
        _stack_library(p1, [wolf, land])  # top: land (mv 0), then wolf (mv 4)

        # choose wolf, then stop.
        _cast_capstone(game, extra_script=[wolf, None])

        assert p1.zones[Zone.BATTLEFIELD].contains(wolf)
        assert p1.zones[Zone.EXILE].contains(land)


class TestParadigmRecurring:
    def _advance_to_p1_main(self, game) -> None:
        for _ in range(30):
            game.advance_phase()
            if (game.phase is Phase.PRECOMBAT_MAIN
                    and game.active_player is game.players[0]):
                return
        raise AssertionError("never reached p1's precombat main")

    def test_copy_cast_each_of_your_first_main_phases(self) -> None:
        game = create_game()
        p1, p2 = game.players
        fillers = [_creature(f"F{i}", 4) for i in range(3)]
        _stack_library(p1, fillers)

        _cast_capstone(game, extra_script=[None])
        assert len(p1.zones[Zone.EXILE]) == 2  # F2 + capstone

        # Next p1 main: accept the copy; it exiles F1 (decline casting it).
        self._advance_to_p1_main(game)
        assert len(game.stack) == 1
        p1._script.extend(["pass", True, "pass", None])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert len(p1.zones[Zone.EXILE]) == 3
        # The copy itself never lands in any zone.
        assert len(p1.zones[Zone.GRAVEYARD]) == 0

        # The trigger recurs on the following turn cycle.
        self._advance_to_p1_main(game)
        assert len(game.stack) == 1
        p1._script.extend(["pass", True, "pass", None])
        p2._script.extend(["pass", "pass"])
        priority_loop(game)
        assert len(p1.zones[Zone.EXILE]) == 4

    def test_decline_copy_nothing_happens(self) -> None:
        game = create_game()
        p1, p2 = game.players
        _stack_library(p1, [_creature("F0", 4), _creature("F1", 4)])

        _cast_capstone(game, extra_script=[None])
        exiled_before = len(p1.zones[Zone.EXILE])

        self._advance_to_p1_main(game)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)

        assert len(p1.zones[Zone.EXILE]) == exiled_before
