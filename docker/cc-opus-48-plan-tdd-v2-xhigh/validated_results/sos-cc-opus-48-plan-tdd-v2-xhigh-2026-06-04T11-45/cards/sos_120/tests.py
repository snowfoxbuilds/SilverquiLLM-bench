"""Tests for SOS 120 — Improvisation Capstone (exile-cast + Paradigm)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game, set_board_state


class _Bolt(Sorcery):
    def __init__(self, victim: Any = None, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))  # cmc 2
        super().__init__(**kwargs)
        self._victim = victim

    def on_resolve(self, game: Any) -> None:
        if self._victim is not None:
            self._victim.life -= 3


def _sorc(name: str, cost: str) -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse(cost))


def _creature(name: str, cost: str) -> Creature:
    return Creature(
        name=name, mana_cost=ManaCost.parse(cost), base_power=2, base_toughness=2
    )


def _drain(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestCapstoneProperties:
    def test_name(self) -> None:
        assert ImprovisationCapstone(owner=None).name == "Improvisation Capstone"

    def test_cost(self) -> None:
        c = ImprovisationCapstone(owner=None)
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")

    def test_is_sorcery_lesson(self) -> None:
        c = ImprovisationCapstone(owner=None)
        assert CardType.SORCERY in c.card_types
        assert "Lesson" in c.subtypes


class TestCapstoneImprovise:
    def test_exiles_until_cmc4_and_casts(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        filler = _creature("Filler", "{9}")
        big = _creature("Big", "{3}")
        bolt = _Bolt(victim=p2)
        lib = p1.zones[Zone.LIBRARY]
        lib.add(filler)  # bottom — must not be exiled
        lib.add(big)     # exiled second (total 5)
        lib.add(bolt)    # top — exiled first (total 2)

        cap.on_resolve(game)
        _drain(game)

        assert p2.life == 17                            # bolt was cast
        assert game.get_battlefield(p1).contains(big)   # creature cast
        assert lib.contains(filler)                     # loop stopped at 4
        assert not lib.contains(bolt) and not lib.contains(big)

    def test_single_big_card_satisfies(self) -> None:
        game = create_game(scripts=([False], []))  # decline casting it
        p1, _ = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        under = _sorc("Under", "{2}")     # would be exiled second if needed
        huge = _sorc("Huge", "{4}{R}")    # cmc 5 — satisfies alone
        lib = p1.zones[Zone.LIBRARY]
        lib.add(under)
        lib.add(huge)  # top — exiled first, total 5 >= 4, stop

        cap.on_resolve(game)
        _drain(game)

        assert lib.contains(under)
        assert game.get_exile(p1).contains(huge)

    def test_lands_not_castable(self) -> None:
        game = create_game(scripts=([True], []))  # only the nonland is offered
        p1, _ = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        land = Land(name="Mountain")
        spell = _sorc("Big", "{4}")  # cmc 4
        lib = p1.zones[Zone.LIBRARY]
        lib.add(spell)  # exiled second (total 4)
        lib.add(land)   # top — exiled first (cmc 0)

        cap.on_resolve(game)
        _drain(game)

        # Land stays in exile, was never cast; only the spell resolved.
        assert game.get_exile(p1).contains(land)
        assert game.get_graveyard(p1).contains(spell)


class TestCapstoneParadigm:
    def test_self_exiles_and_registers_trigger(self) -> None:
        from engine.casting import _resolve_spell
        from engine.stack import StackObject

        game = create_game()
        p1, _ = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        p1.zones[Zone.STACK].add(cap)
        so = StackObject(source=cap, controller=p1)

        _resolve_spell(game, cap, p1, so)

        assert game.get_exile(p1).contains(cap)
        assert not game.get_graveyard(p1).contains(cap)
        regs = game.trigger_manager.get_triggers_for_source(cap)
        assert any(
            r.event_type is BeginningOfMainPhaseTriggeredEvent for r in regs
        )

    def test_paradigm_recurs_on_first_main(self) -> None:
        game = create_game(scripts=([True, True, True], []))
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        # First resolution with empty library: registers the trigger only.
        cap.on_resolve(game)

        bolt = _Bolt(victim=p2)
        big = _creature("Big", "{3}")
        lib = p1.zones[Zone.LIBRARY]
        lib.add(big)
        lib.add(bolt)

        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first=True)
        )
        _drain(game)

        assert p2.life == 17
        assert game.get_battlefield(p1).contains(big)

    def test_paradigm_not_on_second_main(self) -> None:
        game = create_game()
        p1, _ = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first=False)
        )
        assert game.stack.is_empty()

    def test_paradigm_not_on_opponent_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap.on_resolve(game)

        game.active_player_index = 1
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p2, is_first=True)
        )
        assert game.stack.is_empty()
