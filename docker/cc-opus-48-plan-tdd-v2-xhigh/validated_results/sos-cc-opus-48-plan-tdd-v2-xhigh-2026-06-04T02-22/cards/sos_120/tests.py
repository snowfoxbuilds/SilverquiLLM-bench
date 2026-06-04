"""Tests for SOS 120 — Improvisation Capstone (Paradigm)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Sorcery
from engine.types import CardType, ManaType, ManaCost, Phase, Zone
from test_utils import create_game, set_board_state, cast_spell, _resolve_top_of_stack


class _Spell(Sorcery):
    """A no-op sorcery used as library fuel."""

    def __init__(self, name: str, owner: Any, cost: str) -> None:
        super().__init__(name=name, owner=owner, controller=owner,
                         mana_cost=ManaCost.parse(cost))
        self.resolved = False

    def on_resolve(self, game: Any) -> None:
        self.resolved = True


def _fill_library(player: Any, cards: list[Any]) -> None:
    """Add *cards* to *player*'s library; the last item ends up on top."""
    lib = player.zones[Zone.LIBRARY]
    for c in cards:
        c.owner = player
        c.controller = player
        lib.add(c)


CAPSTONE = "Improvisation Capstone"


def _cast_capstone(game: Any) -> None:
    cast_spell(game, 0, CAPSTONE)


class TestProperties:
    def test_is_sorcery(self) -> None:
        c = ImprovisationCapstone(owner=None)
        assert isinstance(c, Sorcery)
        assert CardType.SORCERY in c.card_types

    def test_name_cost_subtype(self) -> None:
        c = ImprovisationCapstone(owner=None)
        assert c.name == "Improvisation Capstone"
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert "Lesson" in c.subtypes


class TestResolveExilesLibrary:
    def test_exiles_top_until_total_mv_four(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        # bottom -> top: keep is bottom, b and a near the top (a is top).
        keep = _Spell("Keep", p1, "{2}")
        b = _Spell("B", p1, "{2}")
        a = _Spell("A", p1, "{2}")
        _fill_library(p1, [keep, b, a])
        # Decline casting each exiled spell (two offers).
        p1._script.extend([False, False])

        _cast_capstone(game)

        exile = p1.zones[Zone.EXILE].get_all()
        assert a in exile and b in exile           # 2 + 2 = 4 -> stop
        assert keep in p1.zones[Zone.LIBRARY].get_all()
        assert a.resolved is False and b.resolved is False

    def test_single_high_mv_card_stops_immediately(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        keep = _Spell("Keep", p1, "{2}")
        big = _Spell("Big", p1, "{5}")  # mv 5 >= 4 alone
        _fill_library(p1, [keep, big])
        p1._script.append(False)  # decline casting Big

        _cast_capstone(game)

        exile = p1.zones[Zone.EXILE].get_all()
        assert big in exile
        assert keep in p1.zones[Zone.LIBRARY].get_all()


class TestFreeCastFromExile:
    def test_chosen_spell_is_cast_for_free_and_resolves(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        boom = _Spell("Boom", p1, "{4}")  # mv 4 -> exiled alone
        _fill_library(p1, [boom])
        p1._script.append(True)  # cast Boom for free

        _cast_capstone(game)

        assert boom.resolved is True
        assert boom in p1.zones[Zone.GRAVEYARD].get_all()
        assert boom not in p1.zones[Zone.EXILE].get_all()


class TestParadigmExilesSelf:
    def test_capstone_goes_to_exile_not_graveyard(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        # Empty library — nothing to exile/cast, isolating the self-exile.

        _cast_capstone(game)

        assert capstone in p1.zones[Zone.EXILE].get_all()
        assert capstone not in p1.zones[Zone.GRAVEYARD].get_all()


def _fire_precombat_main(game: Any, player: Any) -> None:
    """Fire the beginning-of-main-phase event exactly as ``turn.py`` does."""
    from engine.events import BeginningOfMainPhaseTriggeredEvent

    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.trigger_manager.fire_event(
        game, BeginningOfMainPhaseTriggeredEvent(phase=Phase.PRECOMBAT_MAIN)
    )
    _resolve_top_of_stack(game)


def _capstones_in_exile(player: Any) -> list[Any]:
    return [c for c in player.zones[Zone.EXILE].get_all()
            if getattr(c, "name", "") == CAPSTONE]


class TestParadigmRecast:
    def test_copy_castable_at_your_precombat_main(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game)  # first resolution -> sets up Paradigm
        assert capstone in p1.zones[Zone.EXILE].get_all()

        # Library fuel the recast copy will reveal/exile on resolution.
        marker = _Spell("Marker", p1, "{5}")
        _fill_library(p1, [marker])
        # Trigger: cast the copy (yes); copy then declines to cast Marker (no).
        p1._script.extend([True, False])

        _fire_precombat_main(game, p1)

        # The copy resolved: it exiled Marker from the top of the library.
        assert marker in p1.zones[Zone.EXILE].get_all()
        # Original plus the resolved copy now both sit in exile.
        assert len(_capstones_in_exile(p1)) >= 2

    def test_not_triggered_on_opponents_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game)

        marker = _Spell("Marker", p1, "{5}")
        _fill_library(p1, [marker])

        # p2 is the active player — Paradigm should not fire for p1.
        _fire_precombat_main(game, p2)

        assert marker in p1.zones[Zone.LIBRARY].get_all()
        assert len(_capstones_in_exile(p1)) == 1

    def test_paradigm_registered_only_once(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[capstone],
                        mana={ManaType.COLORLESS: 5, ManaType.RED: 2})
        _cast_capstone(game)

        # First main phase: decline casting the copy.
        p1._script.append(False)
        _fire_precombat_main(game, p1)

        # Exactly one Paradigm trigger should be registered (the copy that
        # resolves must not register a second one).
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        triggers = [
            t for t in game.trigger_manager.get_triggers()
            if t.event_type is BeginningOfMainPhaseTriggeredEvent
        ]
        assert len(triggers) == 1
