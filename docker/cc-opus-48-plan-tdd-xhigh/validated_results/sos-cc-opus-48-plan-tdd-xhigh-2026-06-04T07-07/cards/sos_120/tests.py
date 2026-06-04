"""Tests for SOS 120 — Improvisation Capstone ({5}{R}{R} Sorcery — Lesson)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import _resolve_top_of_stack, cast_spell, create_game, set_board_state

_NAME = "Improvisation Capstone"


def _capstone() -> ImprovisationCapstone:
    return ImprovisationCapstone(owner=None)


def _creature(name: str, mv: int) -> Creature:
    return Creature(
        name=name,
        base_power=1,
        base_toughness=1,
        mana_cost=ManaCost.parse("{" + str(mv) + "}"),
    )


def _land(name: str = "Wastes") -> Land:
    return Land(name=name, mana_cost=ManaCost.parse("{0}"))


def _add_to_library(player, *cards: Any) -> None:
    """Add cards bottom→top in argument order (last argument ends on top)."""
    for card in cards:
        card.owner = player
        card.controller = player
        player.zones[Zone.LIBRARY].add(card)


def _capstones_in(zone_container) -> list[ImprovisationCapstone]:
    return [c for c in zone_container.get_all() if isinstance(c, ImprovisationCapstone)]


class TestCapstoneProperties:
    def test_name(self) -> None:
        assert _capstone().name == _NAME

    def test_mana_cost(self) -> None:
        assert _capstone().mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_sorcery_lesson(self) -> None:
        card = _capstone()
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes


class TestCapstoneExile:
    def test_exiles_until_total_mv_4(self) -> None:
        capstone = _capstone()
        game = create_game()
        p1 = game.players[0]
        bottom = _creature("Bottom", mv=2)
        mid = _creature("Mid", mv=2)
        top = _creature("Top", mv=2)
        _add_to_library(p1, bottom, mid, top)
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 7})
        # Decline casting both exiled cards.
        p1._script.append(False)
        p1._script.append(False)
        cast_spell(game, 0, _NAME)
        exile = p1.zones[Zone.EXILE].get_all()
        # Exiled top-first: Top (2), Mid (2) -> total 4, stop before Bottom.
        assert top in exile and mid in exile
        assert bottom in p1.zones[Zone.LIBRARY].get_all()
        # Paradigm: the Capstone itself is exiled, not put in the graveyard.
        assert capstone in exile
        assert capstone not in p1.zones[Zone.GRAVEYARD].get_all()

    def test_casts_chosen_spell_for_free(self) -> None:
        capstone = _capstone()
        game = create_game()
        p1 = game.players[0]
        filler = _creature("Filler", mv=2)
        big = _creature("Big", mv=4)
        _add_to_library(p1, filler, big)
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 7})
        p1._script.append(True)  # cast Big for free
        cast_spell(game, 0, _NAME)
        assert big in game.get_battlefield(p1).get_all()
        assert big not in p1.zones[Zone.EXILE].get_all()
        # Filler was never exiled (threshold hit on Big alone).
        assert filler in p1.zones[Zone.LIBRARY].get_all()

    def test_library_runs_out_before_threshold(self) -> None:
        capstone = _capstone()
        game = create_game()
        p1 = game.players[0]
        only = _creature("Only", mv=2)
        _add_to_library(p1, only)
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 7})
        p1._script.append(False)  # decline casting it
        cast_spell(game, 0, _NAME)
        # Exiling stops when the library empties even though MV < 4.
        assert only in p1.zones[Zone.EXILE].get_all()
        assert p1.zones[Zone.LIBRARY].get_all() == []
        assert capstone in p1.zones[Zone.EXILE].get_all()

    def test_land_among_exiled_is_not_castable(self) -> None:
        capstone = _capstone()
        game = create_game()
        p1 = game.players[0]
        big = _creature("Big", mv=4)
        land = _land("Plains")
        # Library top-first: land (mv0), then big (mv4).
        _add_to_library(p1, big, land)
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 7})
        # Only the creature is offered (single choose_yes_no); cast it.
        p1._script.append(True)
        cast_spell(game, 0, _NAME)
        assert land in p1.zones[Zone.EXILE].get_all()
        assert big in game.get_battlefield(p1).get_all()


class TestCapstoneParadigm:
    def test_paradigm_trigger_registered_once(self) -> None:
        capstone = _capstone()
        game = create_game()
        p1 = game.players[0]
        a = _creature("A", mv=4)
        _add_to_library(p1, a)
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 7})
        p1._script.append(False)  # decline casting A
        cast_spell(game, 0, _NAME)
        main_triggers = [
            t
            for t in game.trigger_manager.get_triggers()
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(main_triggers) == 1
        assert getattr(p1, "_improv_capstone_paradigm", False) is True

    def test_paradigm_casts_free_copy_each_first_main(self) -> None:
        capstone = _capstone()
        game = create_game()
        p1 = game.players[0]
        a = _creature("A", mv=4)
        b = _creature("B", mv=4)
        # Library top-first: A (initial cast), then B (left for the copy).
        _add_to_library(p1, b, a)
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 7})
        p1._script.append(False)  # decline casting A during initial resolution
        cast_spell(game, 0, _NAME)

        # Beginning of the controller's first main phase: cast a free copy.
        game.active_player_index = 0
        p1._script.append(True)   # cast the copy
        p1._script.append(False)  # copy resolves; decline casting B
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=True)
        )
        _resolve_top_of_stack(game)

        exile = p1.zones[Zone.EXILE].get_all()
        assert a in exile and b in exile
        # Only the original Capstone persists in exile; the copy ceased to exist.
        assert len(_capstones_in(p1.zones[Zone.EXILE])) == 1
        assert _capstones_in(p1.zones[Zone.GRAVEYARD]) == []

    def test_paradigm_does_not_trigger_on_postcombat_main(self) -> None:
        capstone = _capstone()
        game = create_game()
        p1 = game.players[0]
        a = _creature("A", mv=4)
        _add_to_library(p1, a)
        set_board_state(game, 0, hand=[capstone], mana={ManaType.RED: 7})
        p1._script.append(False)
        cast_spell(game, 0, _NAME)

        game.active_player_index = 0
        # Postcombat main (is_precombat=False) is NOT "your first main phase".
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_precombat=False)
        )
        assert game.stack.is_empty()
