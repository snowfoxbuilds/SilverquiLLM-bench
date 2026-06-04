"""Tests for SOS 57 — Mana Sculpt (counter + Wizard mana payout)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _push_victim(game: Any, owner: Any, mana_spent: int) -> StackObject:
    victim = Sorcery(name="Victim", mana_cost=ManaCost.parse("{2}{U}{U}"))
    victim.owner = owner
    victim.controller = owner
    victim.mana_spent = mana_spent
    owner.zones[Zone.STACK].add(victim)
    so = StackObject(source=victim, controller=owner)
    game.stack.push(so)
    return so


def _drain(game: Any) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestManaSculptProperties:
    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self) -> None:
        assert CardType.INSTANT in ManaSculpt(owner=None).card_types


class TestManaSculptCounter:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        so = _push_victim(game, p2, mana_spent=4)
        ms = ManaSculpt(owner=p1, controller=p1)
        ms.chosen_targets = [so]
        ms.on_resolve(game)
        assert so not in game.stack.objects()
        assert game.get_graveyard(p2).contains(so.source)

    def test_no_wizard_no_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        so = _push_victim(game, p2, mana_spent=4)
        ms = ManaSculpt(owner=p1, controller=p1)
        ms.chosen_targets = [so]
        ms.on_resolve(game)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first=True)
        )
        _drain(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


class TestManaSculptWizard:
    def test_wizard_adds_mana_next_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Wizard", subtypes={"Wizard"},
                          base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[wizard])
        so = _push_victim(game, p2, mana_spent=4)
        ms = ManaSculpt(owner=p1, controller=p1)
        ms.chosen_targets = [so]
        ms.on_resolve(game)

        # No mana yet — only at the next main phase.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first=True)
        )
        _drain(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

        # One-shot: firing again does not add more.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first=False)
        )
        _drain(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4
