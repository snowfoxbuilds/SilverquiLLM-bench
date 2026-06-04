"""Tests for SOS 120 — Improvisation Capstone (impulse free-cast + Paradigm)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import _resolve_top_of_stack, cast_spell, create_game, set_board_state


class _Spark(Instant):
    """A free-castable instant of configurable mana value; gains 3 life."""

    def __init__(self, mv: int = 2, name: str = "Spark", owner: Any = None) -> None:
        super().__init__(name=name, mana_cost=ManaCost.parse(f"{{{mv}}}"), owner=owner)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _to_library(player: Any, cards: list[Any]) -> None:
    """Place *cards* on the library bottom-to-top (last entry ends on top)."""
    lib = player.zones[Zone.LIBRARY]
    for c in cards:
        c.owner = player
        c.controller = player
        lib.add(c)


def _capstone_count(player: Any, zone: Zone) -> int:
    return sum(
        1 for o in player.zones[zone].get_all() if isinstance(o, ImprovisationCapstone)
    )


class TestCapstoneProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(ImprovisationCapstone(owner=None), Sorcery)

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse(
            "{5}{R}{R}"
        )

    def test_lesson_subtype(self) -> None:
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes


class TestCapstoneImpulse:
    def test_exiles_until_mv_4_and_casts(self) -> None:
        game = create_game()
        p0, _ = game.players
        capstone = ImprovisationCapstone(owner=p0, controller=p0)
        extra = _Spark(mv=2, name="Extra", owner=p0)
        s2 = _Spark(mv=2, name="S2", owner=p0)
        s1 = _Spark(mv=2, name="S1", owner=p0)
        set_board_state(
            game, 0, hand=[capstone], life=20,
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _to_library(p0, [extra, s2, s1])  # s1 on top

        p0._script.extend([True, True])  # cast both exiled spells
        cast_spell(game, 0, "Improvisation Capstone")

        # s1 (2) + s2 (2) reaches 4 → stop; extra stays in library.
        assert game.get_battlefield(p0) is not None
        assert p0.zones[Zone.LIBRARY].contains(extra)
        assert game.get_graveyard(p0).contains(s1)
        assert game.get_graveyard(p0).contains(s2)
        assert p0.life == 26  # two Sparks resolved (+3 each)
        # Paradigm: the Capstone exiled itself rather than going to graveyard.
        assert p0.zones[Zone.EXILE].contains(capstone)
        assert not game.get_graveyard(p0).contains(capstone)

    def test_single_high_mv_card_stops_immediately(self) -> None:
        game = create_game()
        p0, _ = game.players
        capstone = ImprovisationCapstone(owner=p0, controller=p0)
        below = _Spark(mv=2, name="Below", owner=p0)
        big = _Spark(mv=5, name="Big", owner=p0)
        set_board_state(
            game, 0, hand=[capstone], life=20,
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _to_library(p0, [below, big])  # big on top

        p0._script.extend([True])  # cast the single exiled spell
        cast_spell(game, 0, "Improvisation Capstone")

        assert p0.zones[Zone.LIBRARY].contains(below)  # only one card milled
        assert game.get_graveyard(p0).contains(big)
        assert p0.life == 23

    def test_small_library_exiles_what_is_there(self) -> None:
        game = create_game()
        p0, _ = game.players
        capstone = ImprovisationCapstone(owner=p0, controller=p0)
        only = _Spark(mv=2, name="Only", owner=p0)
        set_board_state(
            game, 0, hand=[capstone], life=20,
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _to_library(p0, [only])

        p0._script.extend([False])  # decline to cast it
        cast_spell(game, 0, "Improvisation Capstone")

        assert len(p0.zones[Zone.LIBRARY]) == 0  # exhausted without reaching 4
        assert p0.zones[Zone.EXILE].contains(only)  # exiled, not cast


class TestCapstoneParadigm:
    def test_recasts_copy_on_first_main_phase(self) -> None:
        game = create_game()
        p0, _ = game.players
        capstone = ImprovisationCapstone(owner=p0, controller=p0)
        c1 = _Spark(mv=2, name="C1", owner=p0)
        c2 = _Spark(mv=2, name="C2", owner=p0)
        c3 = _Spark(mv=2, name="C3", owner=p0)
        c4 = _Spark(mv=2, name="C4", owner=p0)
        set_board_state(
            game, 0, hand=[capstone], life=20,
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _to_library(p0, [c4, c3, c2, c1])  # c1 on top

        # First cast: decline both mills. Then main-phase trigger casts a copy
        # which mills c3 + c4 (declined too).
        p0._script.extend([False, False, True, False, False])
        cast_spell(game, 0, "Improvisation Capstone")
        assert _capstone_count(p0, Zone.EXILE) == 1  # only the original so far

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p0, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_top_of_stack(game)

        assert len(p0.zones[Zone.LIBRARY]) == 0  # copy milled the rest
        assert _capstone_count(p0, Zone.EXILE) == 2  # original + the cast copy

    def test_no_recast_on_postcombat_main(self) -> None:
        game = create_game()
        p0, _ = game.players
        capstone = ImprovisationCapstone(owner=p0, controller=p0)
        c1 = _Spark(mv=2, name="C1", owner=p0)
        c2 = _Spark(mv=2, name="C2", owner=p0)
        leftover = _Spark(mv=2, name="Leftover", owner=p0)
        set_board_state(
            game, 0, hand=[capstone], life=20,
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )
        _to_library(p0, [leftover, c2, c1])  # c1 on top

        p0._script.extend([False, False])  # decline both first-cast mills
        cast_spell(game, 0, "Improvisation Capstone")
        lib_before = len(p0.zones[Zone.LIBRARY])

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p0, phase=Phase.POSTCOMBAT_MAIN),
        )
        _resolve_top_of_stack(game)

        # Second main phase is not a "first" main phase → no copy cast.
        assert len(p0.zones[Zone.LIBRARY]) == lib_before
        assert _capstone_count(p0, Zone.EXILE) == 1
