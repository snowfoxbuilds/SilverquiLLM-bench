"""Tests for Improvisation Capstone (SOS 120)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game


class _GainLifeInstant(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Surge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 3


def _spell(name, cost):
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _set_library(player, cards_top_first):
    lib = player.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in reversed(cards_top_first):
        c.owner = player
        c.controller = player
        lib.add(c)


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes


class TestImprovise:
    def test_exile_stops_at_threshold(self) -> None:
        game = create_game()
        p1, _ = game.players
        a, b, c = _spell("A", "{2}"), _spell("B", "{3}"), _spell("C", "{1}")
        _set_library(p1, [a, b, c])  # a is top
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([False, False])  # decline casting a and b
        cap.on_resolve(game)
        # 2 + 3 = 5 >= 4 -> exile a and b only; c remains in library.
        assert p1.zones[Zone.EXILE].contains(a)
        assert p1.zones[Zone.EXILE].contains(b)
        assert p1.zones[Zone.LIBRARY].contains(c)
        assert not p1.zones[Zone.EXILE].contains(c)

    def test_single_high_mv_card_stops_immediately(self) -> None:
        game = create_game()
        p1, _ = game.players
        big, rest = _spell("Big", "{4}"), _spell("Rest", "{2}")
        _set_library(p1, [big, rest])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([False])  # decline big
        cap.on_resolve(game)
        assert p1.zones[Zone.EXILE].contains(big)
        assert p1.zones[Zone.LIBRARY].contains(rest)

    def test_free_cast_resolves(self) -> None:
        game = create_game()
        p1, _ = game.players
        p1.life = 20
        surge = _GainLifeInstant(owner=p1, controller=p1)
        filler = _spell("Filler", "{4}")
        _set_library(p1, [surge, filler])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1._script.extend([True, False])  # cast surge, decline filler
        cap.on_resolve(game)
        _resolve_stack(game)
        assert p1.life == 23
        assert p1.zones[Zone.GRAVEYARD].contains(surge)
        assert p1.zones[Zone.EXILE].contains(filler)

    def test_empty_library_noop(self) -> None:
        game = create_game()
        p1, _ = game.players
        _set_library(p1, [])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        assert p1.remaining_choices == 0


class TestParadigm:
    def test_capstone_exiled_on_real_resolution(self) -> None:
        game = create_game()
        p1, _ = game.players
        _set_library(p1, [_spell("X", "{4}")])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.HAND].add(cap)
        cap.owner = p1
        cap.controller = p1
        p1._script.extend([False])  # decline casting X
        from engine.casting import cast_spell_free
        cast_spell_free(game, p1, cap, Zone.HAND)
        _resolve_stack(game)
        assert p1.zones[Zone.EXILE].contains(cap)
        assert not p1.zones[Zone.GRAVEYARD].contains(cap)

    def test_paradigm_recurs_next_main(self) -> None:
        game = create_game()
        p1, _ = game.players
        # First resolution arms Paradigm (empty library -> no exiles).
        _set_library(p1, [])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        # Refill library for the recurring copy to exile from.
        refill = _spell("Y", "{4}")
        _set_library(p1, [refill])
        # Fire the controller's first main phase; cast a copy, decline its cast.
        p1._script.extend([True, False])
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=True))
        _resolve_stack(game)
        # The copy exiled the refill card.
        assert p1.zones[Zone.EXILE].contains(refill)
        assert not p1.zones[Zone.LIBRARY].contains(refill)

    def test_paradigm_not_on_postcombat_main(self) -> None:
        game = create_game()
        p1, _ = game.players
        _set_library(p1, [])
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)
        refill = _spell("Z", "{4}")
        _set_library(p1, [refill])
        # Second main phase (is_first_main=False) should NOT trigger Paradigm.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=False))
        _resolve_stack(game)
        assert p1.zones[Zone.LIBRARY].contains(refill)
        assert p1.remaining_choices == 0
