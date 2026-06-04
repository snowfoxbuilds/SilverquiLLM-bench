"""Tests for Mana Sculpt (SOS 57)."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _enemy_spell_on_stack(game, p2, *, mana_spent=None, cmc_cost="{5}"):
    spell = Sorcery(name="EnemySpell", mana_cost=ManaCost.parse(cmc_cost),
                    owner=p2, controller=p2)
    if mana_spent is not None:
        spell.mana_spent = mana_spent
    stack_obj = StackObject(source=spell, controller=p2)
    game.stack.push(stack_obj)
    return spell, stack_obj


class TestProperties:
    def test_static_data(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")
        assert CardType.INSTANT in card.card_types


class TestCanCast:
    def test_can_cast_with_enemy_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ManaSculpt(owner=p1, controller=p1)
        _enemy_spell_on_stack(game, p2)
        assert card.can_cast(game) is True

    def test_cannot_cast_empty_stack(self) -> None:
        game = create_game()
        p1, _ = game.players
        card = ManaSculpt(owner=p1, controller=p1)
        assert card.can_cast(game) is False


class TestCounter:
    def test_counters_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ManaSculpt(owner=p1, controller=p1)
        spell, stack_obj = _enemy_spell_on_stack(game, p2, mana_spent=5)
        card.chosen_targets = [stack_obj]
        card.on_resolve(game)
        # Spell left the stack and went to its owner's graveyard.
        assert stack_obj not in game.stack._items
        assert game.get_graveyard(p2).contains(spell)


class TestDelayedMana:
    def test_wizard_adds_mana_next_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Wiz", base_power=1, base_toughness=1,
                          subtypes={"Wizard"}, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])
        card = ManaSculpt(owner=p1, controller=p1)
        _spell, stack_obj = _enemy_spell_on_stack(game, p2, mana_spent=4)
        card.chosen_targets = [stack_obj]
        card.on_resolve(game)
        # No mana yet.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        # Fire controller's main phase.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=True))
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_one_shot(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Wiz", base_power=1, base_toughness=1,
                          subtypes={"Wizard"}, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])
        card = ManaSculpt(owner=p1, controller=p1)
        _spell, stack_obj = _enemy_spell_on_stack(game, p2, mana_spent=3)
        card.chosen_targets = [stack_obj]
        card.on_resolve(game)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=True))
        _resolve_stack(game)
        p1.mana_pool.empty()
        # Second main phase — trigger already unregistered.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=False))
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_not_opponent_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Wiz", base_power=1, base_toughness=1,
                          subtypes={"Wizard"}, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])
        card = ManaSculpt(owner=p1, controller=p1)
        _spell, stack_obj = _enemy_spell_on_stack(game, p2, mana_spent=4)
        card.chosen_targets = [stack_obj]
        card.on_resolve(game)
        # Opponent's main phase should not add mana to p1.
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p2, is_first_main=True))
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_no_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ManaSculpt(owner=p1, controller=p1)
        _spell, stack_obj = _enemy_spell_on_stack(game, p2, mana_spent=4)
        card.chosen_targets = [stack_obj]
        card.on_resolve(game)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=True))
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_amount_falls_back_to_cmc(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(name="Wiz", base_power=1, base_toughness=1,
                          subtypes={"Wizard"}, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[wizard])
        card = ManaSculpt(owner=p1, controller=p1)
        # No mana_spent set -> fall back to mana_cost.cmc ({6} -> 6).
        _spell, stack_obj = _enemy_spell_on_stack(game, p2, cmc_cost="{6}")
        card.chosen_targets = [stack_obj]
        card.on_resolve(game)
        game.trigger_manager.fire_event(
            game, BeginningOfMainPhaseTriggeredEvent(player=p1, is_first_main=True))
        _resolve_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 6
