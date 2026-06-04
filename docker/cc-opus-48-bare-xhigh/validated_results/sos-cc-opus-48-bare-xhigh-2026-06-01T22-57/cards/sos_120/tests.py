"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.casting import resolve_top
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestProperties:
    def test_basics(self) -> None:
        c = ImprovisationCapstone(owner=None)
        assert c.name == "Improvisation Capstone"
        assert c.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert isinstance(c, Sorcery)
        assert "Lesson" in c.subtypes


class TestCapstone:
    def test_exiles_until_threshold_and_casts(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        spell = Sorcery(name="Free", mana_cost=ManaCost.parse("{4}"))  # MV 4
        p1.zones[Zone.LIBRARY].add(spell)  # on top
        p1._script.extend([True, spell])  # cast it for free
        cap.on_resolve(game)
        # Exiled then free-cast → no longer in the library, now on the stack.
        assert spell not in p1.zones[Zone.LIBRARY].get_all()
        assert not game.stack.is_empty()
        # Paradigm bookkeeping.
        assert cap._paradigm_registered is True
        assert cap._replace_graveyard_with_exile is True

    def test_decline_to_cast(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        spell = Sorcery(name="Free", mana_cost=ManaCost.parse("{4}"))
        p1.zones[Zone.LIBRARY].add(spell)
        p1._script.extend([False])  # decline casting
        cap.on_resolve(game)
        # Exiled but not cast.
        assert spell in p1.zones[Zone.EXILE].get_all()
        assert game.stack.is_empty()


class TestParadigm:
    def test_recast_copy_at_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        # Simulate the resolved spell sitting in exile.
        cap._register_paradigm(game)
        p1.zones[Zone.EXILE].add(cap)
        p1._script.extend([True])  # cast a copy
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, precombat=True)
        )
        resolve_top(game)  # resolve the Paradigm trigger → push the copy
        assert not game.stack.is_empty()
        top = game.stack.peek()
        assert getattr(top.source, "_is_paradigm_copy", False) is True

    def test_no_recast_postcombat(self) -> None:
        game = create_game()
        p1 = game.players[0]
        cap = ImprovisationCapstone(owner=p1, controller=p1)
        cap._register_paradigm(game)
        p1.zones[Zone.EXILE].add(cap)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, precombat=False)
        )
        assert game.stack.is_empty()
