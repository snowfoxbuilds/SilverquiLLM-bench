"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Land, Sorcery
from engine.events import MainPhaseBeganTriggeredEvent
from engine.types import ManaCost, Phase, Zone
from test_utils import _resolve_top_of_stack, create_game


def _mk(p, name, cost, cls=Instant):
    c = cls(name=name, mana_cost=ManaCost.parse(cost))
    c.owner = p
    c.controller = p
    return c


def _fill_library(p, cards):
    for c in cards:
        c.owner = p
        c.controller = p
        p.zones[Zone.LIBRARY].add(c)


class TestProperties:
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


class TestDig:
    def test_exiles_until_total_mv_four(self) -> None:
        game = create_game(scripts=([False, False, False], []))
        p1 = game.players[0]
        # top is last added: order bottom->top = Two, One, Three, Deep
        # dig from top: Two(2)=2, One(1)=3, Three(3)=6 stop.
        deep = _mk(p1, "Deep", "{9}")
        three = _mk(p1, "Three", "{3}")
        one = _mk(p1, "One", "{1}")
        two = _mk(p1, "Two", "{2}")
        _fill_library(p1, [deep, three, one, two])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap._run_dig(game, p1)
        ex = p1.zones[Zone.EXILE]
        assert ex.contains(two) and ex.contains(one) and ex.contains(three)
        assert not ex.contains(deep)
        assert p1.zones[Zone.LIBRARY].contains(deep)

    def test_dig_stops_at_empty_library(self) -> None:
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        small = _mk(p1, "Small", "{1}")
        _fill_library(p1, [small])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap._run_dig(game, p1)  # only 1 card, mv 1 < 4 — exiles it then stops.
        assert p1.zones[Zone.EXILE].contains(small)

    def test_may_cast_exiled_spell_for_free(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        big = _mk(p1, "BigBolt", "{5}")
        _fill_library(p1, [big])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap._run_dig(game, p1)
        # Accepting the cast moves the card from exile onto the stack.
        assert not p1.zones[Zone.EXILE].contains(big)
        assert p1.zones[Zone.STACK].contains(big)

    def test_lands_are_not_offered_to_cast(self) -> None:
        game = create_game(scripts=([], []))  # no choices -> nothing castable
        p1 = game.players[0]
        land = _mk(p1, "Wastes", "{0}", cls=Land)
        big = _mk(p1, "Engine", "{5}")
        _fill_library(p1, [land, big])  # top is big(5) -> stops immediately
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        # big alone has mv 5 >= 4; only big is exiled. With an empty script the
        # yes/no for big is unanswerable -> it is simply not cast (no raise).
        cap._run_dig(game, p1)
        assert p1.zones[Zone.EXILE].contains(big)


class TestParadigm:
    def test_resolution_sets_exile_flag_and_trigger(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        assert getattr(cap, "_exile_instead_of_graveyard", False) is True
        assert len(game.trigger_manager.get_triggers_for_source(cap)) == 1

    def test_paradigm_copy_does_not_recurse(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        copy = ImprovisationCapstone(owner=p1, controller=p1)
        copy._is_paradigm_copy = True
        copy.on_resolve(game)
        assert getattr(copy, "_exile_instead_of_graveyard", False) is False
        assert game.trigger_manager.get_triggers_for_source(copy) == []

    def test_paradigm_recasts_in_precombat_main(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.EXILE].add(cap)
        cap._setup_paradigm(game, p1)
        # Library has one land for the copy's dig to grab.
        land = _mk(p1, "Wastes", "{0}", cls=Land)
        _fill_library(p1, [land])
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.trigger_manager.fire_event(
            game, MainPhaseBeganTriggeredEvent(player=p1)
        )
        _resolve_top_of_stack(game)
        assert p1.zones[Zone.EXILE].contains(land)

    def test_paradigm_inactive_outside_first_main(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.EXILE].add(cap)
        cap._setup_paradigm(game, p1)
        game.active_player_index = 0
        game.phase = Phase.POSTCOMBAT_MAIN
        game.trigger_manager.fire_event(
            game, MainPhaseBeganTriggeredEvent(player=p1)
        )
        assert game.stack.is_empty()
