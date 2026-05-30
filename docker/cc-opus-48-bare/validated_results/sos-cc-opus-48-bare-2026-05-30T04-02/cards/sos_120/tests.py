"""Tests for SOS 120 — Improvisation Capstone (Paradigm)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, Phase, Zone
from test_utils import create_game, set_board_state


def _capstone(player: Any) -> ImprovisationCapstone:
    return ImprovisationCapstone(owner=player, controller=player)


def _spell(player: Any, name: str, cmc: int) -> Instant:
    return Instant(name=name, owner=player, controller=player, mana_cost=ManaCost(generic=cmc))


def _creature(player: Any, name: str, cmc: int) -> Creature:
    return Creature(
        name=name,
        owner=player,
        controller=player,
        mana_cost=ManaCost(generic=cmc),
        base_power=2,
        base_toughness=2,
    )


def _set_library(game: Any, player: Any, cards: list[Any]) -> None:
    """Place *cards* into a player's library (last item is the top)."""
    library = player.zones[Zone.LIBRARY]
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _resolve_stack(game: Any) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _main_phase_triggers(game: Any) -> list[Any]:
    return [
        t
        for t in game.trigger_manager.get_triggers()
        if t.event_type is BeginningOfMainPhaseTriggeredEvent
    ]


def _capstone_copies_in_exile(player: Any) -> list[Any]:
    return [
        o
        for o in player.zones[Zone.EXILE].get_all()
        if getattr(o, "name", None) == "Improvisation Capstone"
    ]


class TestCapstoneProperties:
    def test_name(self) -> None:
        assert ImprovisationCapstone().name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone().mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_types_and_colors(self) -> None:
        c = ImprovisationCapstone()
        assert CardType.SORCERY in c.card_types
        assert "Lesson" in c.subtypes
        assert c.colors == ["R"]


class TestMainEffect:
    def test_exiles_until_total_mv_at_least_four(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        # Top of library is the last element: [bottom a, b, c top].
        a = _spell(p1, "A", 2)
        b = _spell(p1, "B", 2)
        c = _spell(p1, "C", 2)
        _set_library(game, p1, [a, b, c])

        cap.on_resolve(game)

        # Exiles C (2) then B (2 → total 4) and stops; A stays in the library.
        assert p1.zones[Zone.EXILE].contains(c)
        assert p1.zones[Zone.EXILE].contains(b)
        assert p1.zones[Zone.LIBRARY].contains(a)
        assert not p1.zones[Zone.EXILE].contains(a)

    def test_stops_as_soon_as_threshold_met(self) -> None:
        game = create_game(scripts=([False], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        big = _spell(p1, "Big", 5)
        small = _spell(p1, "Small", 1)
        _set_library(game, p1, [small, big])  # Big is on top

        cap.on_resolve(game)

        # A single 5-MV card already meets the threshold.
        assert p1.zones[Zone.EXILE].contains(big)
        assert p1.zones[Zone.LIBRARY].contains(small)

    def test_handles_empty_library(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])

        cap.on_resolve(game)  # must not raise

        assert len(p1.zones[Zone.EXILE]) == 0

    def test_may_cast_exiled_spell_for_free(self) -> None:
        game = create_game(scripts=([True], []))  # cast the exiled creature
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        bear = _creature(p1, "Bear", 4)  # MV 4 meets the threshold alone
        _set_library(game, p1, [bear])

        cap.on_resolve(game)
        _resolve_stack(game)

        # The free-cast creature resolved onto the battlefield.
        assert game.get_battlefield(p1).contains(bear)

    def test_uncast_exiled_spells_remain_in_exile(self) -> None:
        game = create_game(scripts=([False], []))  # decline to cast
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        bear = _creature(p1, "Bear", 4)
        _set_library(game, p1, [bear])

        cap.on_resolve(game)
        _resolve_stack(game)

        assert p1.zones[Zone.EXILE].contains(bear)
        assert not game.get_battlefield(p1).contains(bear)


class TestParadigm:
    def test_spell_redirected_to_exile(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])

        cap.on_resolve(game)

        # Paradigm's "Exile this spell" sets the redirect flag the resolver reads.
        assert cap._exile_instead_of_graveyard is True

    def test_first_resolution_registers_recast_trigger(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])

        assert _main_phase_triggers(game) == []
        cap.on_resolve(game)
        assert len(_main_phase_triggers(game)) == 1

    def test_paradigm_setup_only_once(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])

        cap.on_resolve(game)
        cap.on_resolve(game)
        # A second resolution of a same-named spell does not add another trigger.
        assert len(_main_phase_triggers(game)) == 1

    def test_recast_copy_at_precombat_main(self) -> None:
        # Script: cast the recast copy (True), then cast the bear it digs up (True).
        game = create_game(scripts=([True, True], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])  # first resolution digs up nothing

        cap.on_resolve(game)

        # Stock the library so the recast copy's main effect has something to do.
        bear = _creature(p1, "Bear", 4)
        _set_library(game, p1, [bear])

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)

        # The recast copy resolved and free-cast the bear onto the battlefield.
        assert game.get_battlefield(p1).contains(bear)
        # The token copy cleaned itself up — no stray copy lingers in exile.
        assert _capstone_copies_in_exile(p1) == []

    def test_no_recast_when_declined(self) -> None:
        game = create_game(scripts=([False], []))  # decline the recast
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])

        cap.on_resolve(game)
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)

        # Declined copy is created in exile then swept by the token SBA.
        assert _capstone_copies_in_exile(p1) == []

    def test_no_recast_on_postcombat_main(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])

        cap.on_resolve(game)
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.POSTCOMBAT_MAIN),
        )
        _resolve_stack(game)

        assert _capstone_copies_in_exile(p1) == []

    def test_no_recast_on_opponents_main(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        cap = _capstone(p1)
        set_board_state(game, 0, battlefield=[cap])
        _set_library(game, p1, [])

        cap.on_resolve(game)
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p2, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)

        assert _capstone_copies_in_exile(p1) == []
