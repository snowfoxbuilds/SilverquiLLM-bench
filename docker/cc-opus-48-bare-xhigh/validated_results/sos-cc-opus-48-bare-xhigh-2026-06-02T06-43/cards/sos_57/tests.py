"""Tests for Mana Sculpt (SOS 57)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state


def _put_spell_on_stack(game: Any, caster: Any, card: Any) -> StackObject:
    """Place *card* on the stack as a spell controlled by *caster*."""
    card.owner = caster
    card.controller = caster
    caster.zones[Zone.STACK].add(card)
    stack_obj = StackObject(source=card, controller=caster)
    game.stack.push(stack_obj)
    return stack_obj


def _wizard(name: str = "Wiz") -> Creature:
    return Creature(name=name, base_power=1, base_toughness=1, subtypes={"Wizard"})


class TestManaSculptProperties:
    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)
        assert CardType.INSTANT in ManaSculpt(owner=None).card_types

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    def test_cannot_cast_empty_stack(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=game.players[0]).can_cast(game) is False

    def test_can_cast_with_spell_on_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = Sorcery(name="Foo", mana_cost=ManaCost.parse("{2}"))
        _put_spell_on_stack(game, p2, spell)
        assert ManaSculpt(owner=p1).can_cast(game) is True

    def test_get_targets_empty_stack(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=game.players[0]).get_targets(game) == []

    def test_get_targets_returns_stack_requirement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = Sorcery(name="Foo", mana_cost=ManaCost.parse("{2}"))
        _put_spell_on_stack(game, p2, spell)
        reqs = ManaSculpt(owner=p1).get_targets(game)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK

    def test_does_not_target_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        _put_spell_on_stack(game, p1, sculpt)
        # Only Mana Sculpt is on the stack — nothing else to counter.
        assert sculpt.can_cast(game) is False
        assert sculpt.get_targets(game) == []


class TestManaSculptResolution:
    def test_counters_target_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = Sorcery(name="Foo", mana_cost=ManaCost.parse("{2}"))
        stack_obj = _put_spell_on_stack(game, p2, spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        assert stack_obj not in game.stack._items
        assert not p2.zones[Zone.STACK].contains(spell)
        assert p2.zones[Zone.GRAVEYARD].contains(spell)

    def test_no_target_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = []
        # Should not raise.
        sculpt.on_resolve(game)

    def test_no_wizard_no_delayed_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = Sorcery(name="Foo", mana_cost=ManaCost.parse("{3}"))
        stack_obj = _put_spell_on_stack(game, p2, spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, phase=game.phase)
        )
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_wizard_adds_colorless_at_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        spell = Sorcery(name="Foo", mana_cost=ManaCost.parse("{4}"))
        stack_obj = _put_spell_on_stack(game, p2, spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # No mana yet — only at the next main phase.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, phase=game.phase)
        )
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_delayed_mana_only_for_controller(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        spell = Sorcery(name="Foo", mana_cost=ManaCost.parse("{4}"))
        stack_obj = _put_spell_on_stack(game, p2, spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        # Opponent's main phase should not grant the mana.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p2, phase=game.phase)
        )
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

        # Controller's main phase grants it.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, phase=game.phase)
        )
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_delayed_mana_is_one_shot(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        spell = Sorcery(name="Foo", mana_cost=ManaCost.parse("{4}"))
        stack_obj = _put_spell_on_stack(game, p2, spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        for _ in range(2):
            game.trigger_manager.fire_event(
                game, BeginningOfMainPhaseTriggeredEvent(player=p1, phase=game.phase)
            )
            _resolve_stack(game)

        # Only the first main phase grants mana — total is 4, not 8.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_colored_spell_mana_value(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[_wizard()])
        spell = Instant(name="Bolt", mana_cost=ManaCost.parse("{2}{U}{U}"))
        stack_obj = _put_spell_on_stack(game, p2, spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [stack_obj]
        sculpt.on_resolve(game)

        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, phase=game.phase)
        )
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4


def _resolve_stack(game: Any) -> None:
    """Resolve all objects currently on the stack (LIFO)."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
