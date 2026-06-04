"""Tests for Improvisation Capstone (SOS 120)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import (
    ImprovisationCapstone,
    exile_until_mana_value,
)
from engine.card import Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, Phase, Zone
from test_utils import card_colors, create_game


class _Pinger(Instant):
    def __init__(self, name: str = "Pinger", mv: int = 2, **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse(f"{{{mv}}}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        game._resolved = getattr(game, "_resolved", 0) + 1


def _vanilla(name: str, mv: int = 2) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(f"{{{mv}}}"))


def _resolve_stack(game: Any) -> None:
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


def _add_library(player: Any, cards: list) -> None:
    lib = player.zones[Zone.LIBRARY]
    for c in cards:  # last card ends up on top
        c.owner = player
        c.controller = player
        lib.add(c)


class TestCapstoneProperties:
    def test_is_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types

    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_mana_cost(self) -> None:
        assert ImprovisationCapstone(owner=None).mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_lesson_subtype(self) -> None:
        assert "Lesson" in ImprovisationCapstone(owner=None).subtypes

    def test_red(self) -> None:
        assert card_colors(ImprovisationCapstone(owner=None)) == {"R"}

    def test_starts_not_a_copy(self) -> None:
        assert ImprovisationCapstone(owner=None).is_paradigm_copy is False


class TestExileUntilManaValue:
    def test_stops_at_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        a, b, c = _vanilla("a"), _vanilla("b"), _vanilla("c")  # each MV 2
        _add_library(p1, [c, b, a])  # a on top
        exiled = exile_until_mana_value(game, p1, 4)
        # a (2) + b (2) = 4 -> stop. c remains in library.
        assert exiled == [a, b]
        assert p1.zones[Zone.EXILE].contains(a)
        assert p1.zones[Zone.EXILE].contains(b)
        assert p1.zones[Zone.LIBRARY].contains(c)

    def test_single_big_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        big = _vanilla("Big", mv=5)
        _add_library(p1, [big])
        exiled = exile_until_mana_value(game, p1, 4)
        assert exiled == [big]

    def test_empty_library_no_crash(self) -> None:
        game = create_game()
        p1 = game.players[0]
        assert exile_until_mana_value(game, p1, 4) == []

    def test_exhausts_library_when_below_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        a, b = _vanilla("a", mv=1), _vanilla("b", mv=1)
        _add_library(p1, [b, a])
        exiled = exile_until_mana_value(game, p1, 4)
        assert set(exiled) == {a, b}
        assert len(p1.zones[Zone.LIBRARY]) == 0


class TestCapstoneMainEffect:
    def test_casts_chosen_spells_for_free(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        top, second = _Pinger("Top"), _Pinger("Second")
        _add_library(p1, [second, top])  # top on top; both MV 2 -> total 4
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        _resolve_stack(game)
        assert game._resolved == 2
        assert p1.zones[Zone.GRAVEYARD].contains(top)
        assert p1.zones[Zone.GRAVEYARD].contains(second)

    def test_decline_leaves_in_exile(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        top, second = _Pinger("Top"), _Pinger("Second")
        _add_library(p1, [second, top])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        _resolve_stack(game)
        assert getattr(game, "_resolved", 0) == 0
        assert p1.zones[Zone.EXILE].contains(top)
        assert p1.zones[Zone.EXILE].contains(second)


class TestParadigm:
    def test_arms_paradigm_on_resolve(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)  # empty library
        assert cap.replace_graveyard_with_exile is True
        assert len(game.trigger_manager.get_triggers_for_source(cap)) == 1

    def test_copy_does_not_arm(self) -> None:
        game = create_game()
        p1 = game.players[0]
        copy = ImprovisationCapstone(owner=p1, controller=p1)
        copy.is_paradigm_copy = True
        copy.on_resolve(game)
        assert getattr(copy, "replace_graveyard_with_exile", False) is False
        assert len(game.trigger_manager.get_triggers_for_source(copy)) == 0

    def test_recurs_on_first_main(self) -> None:
        # script: yes to cast a copy, then yes to cast the exiled pinger.
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.EXILE].add(cap)
        cap._register_paradigm(game)
        pinger = _Pinger("Recur", mv=4)
        _add_library(p1, [pinger])
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_stack(game)
        assert game._resolved == 1

    def test_skips_postcombat_main(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.EXILE].add(cap)
        cap._register_paradigm(game)
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.POSTCOMBAT_MAIN),
        )
        assert game.stack.is_empty()

    def test_only_controller_triggers(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.EXILE].add(cap)
        cap._register_paradigm(game)
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p2, phase=Phase.PRECOMBAT_MAIN),
        )
        assert game.stack.is_empty()
