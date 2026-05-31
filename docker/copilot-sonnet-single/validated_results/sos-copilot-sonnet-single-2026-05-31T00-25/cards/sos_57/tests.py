"""Tests for Mana Sculpt (sos_57)."""
from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestManaSculptProperties:
    def test_name(self):
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"

    def test_mana_cost(self):
        card = ManaSculpt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self):
        card = ManaSculpt(owner=None)
        assert CardType.INSTANT in card.card_types
        assert isinstance(card, Instant)

    def test_mana_to_add_defaults_zero(self):
        card = ManaSculpt(owner=None)
        assert card.mana_to_add == 0


class TestManaSculptCounterSpell:
    def _push_spell_to_stack(self, game, player, spell):
        """Helper to put a spell on the game stack."""
        from engine.stack import StackObject
        so = StackObject(
            source=spell,
            controller=player,
            on_resolve=lambda g: None,
        )
        game.stack.push(so)
        player.zones[Zone.STACK].add(spell)
        return so

    def test_counters_target_spell(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put a spell on the stack for p2
        enemy_spell = Sorcery(name="EnemySpell", owner=p2, controller=p2)
        so = self._push_spell_to_stack(game, p2, enemy_spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [so]
        sculpt.on_resolve(game)

        # Stack should now be empty
        assert len(game.stack._items) == 0

    def test_countered_spell_goes_to_graveyard(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        enemy_spell = Sorcery(name="EnemySpell", owner=p2, controller=p2)
        so = self._push_spell_to_stack(game, p2, enemy_spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [so]
        sculpt.on_resolve(game)

        gy = p2.zones[Zone.GRAVEYARD]
        assert gy.contains(enemy_spell)

    def test_no_target_does_nothing(self):
        game = create_game()
        p1 = game.players[0]

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = []
        # Should not raise
        sculpt.on_resolve(game)

    def test_can_cast_only_when_spell_on_stack(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        sculpt = ManaSculpt(owner=p1, controller=p1)
        assert sculpt.can_cast(game) is False

        enemy_spell = Sorcery(name="EnemySpell", owner=p2, controller=p2)
        self._push_spell_to_stack(game, p2, enemy_spell)
        assert sculpt.can_cast(game) is True


class TestManaSculptWizardBonus:
    def _push_spell_to_stack(self, game, player, spell):
        from engine.stack import StackObject
        so = StackObject(
            source=spell,
            controller=player,
            on_resolve=lambda g: None,
        )
        game.stack.push(so)
        player.zones[Zone.STACK].add(spell)
        return so

    def test_no_wizard_no_mana_trigger(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        enemy_spell = Sorcery(name="EnemySpell", owner=p2, controller=p2)
        enemy_spell.mana_cost = ManaCost.parse("{3}")
        so = self._push_spell_to_stack(game, p2, enemy_spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [so]
        sculpt.on_resolve(game)

        # No wizard, no trigger registered
        assert len(game.trigger_manager._triggers) == 0

    def test_with_wizard_registers_upkeep_trigger(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = Creature(
            name="Wizard Helper",
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
            owner=p1, controller=p1,
        )
        set_board_state(game, 0, battlefield=[wizard])

        enemy_spell = Sorcery(name="EnemySpell", owner=p2, controller=p2)
        enemy_spell.mana_cost = ManaCost.parse("{3}")
        so = self._push_spell_to_stack(game, p2, enemy_spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [so]
        sculpt.on_resolve(game)

        # A trigger should be registered
        assert len(game.trigger_manager._triggers) == 1

    def test_with_wizard_trigger_fires_and_adds_mana(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = Creature(
            name="Wizard Helper",
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
            owner=p1, controller=p1,
        )
        set_board_state(game, 0, battlefield=[wizard])

        enemy_spell = Sorcery(name="EnemySpell", owner=p2, controller=p2)
        enemy_spell.mana_cost = ManaCost.parse("{3}")
        so = self._push_spell_to_stack(game, p2, enemy_spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [so]
        sculpt.on_resolve(game)

        # Set p1 as active player so the trigger fires for them
        game.active_player_index = 0

        from engine.events import BeginningOfUpkeepTriggeredEvent
        mana_before = p1.mana_pool.get(ManaType.COLORLESS)
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        # Resolve the triggered ability from the stack
        while game.stack._items:
            top = game.stack._items.pop()
            top.on_resolve(game)

        mana_after = p1.mana_pool.get(ManaType.COLORLESS)
        assert mana_after - mana_before == 3

    def test_with_wizard_trigger_only_fires_once(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        wizard = Creature(
            name="Wizard Helper",
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
            owner=p1, controller=p1,
        )
        set_board_state(game, 0, battlefield=[wizard])

        enemy_spell = Sorcery(name="EnemySpell", owner=p2, controller=p2)
        enemy_spell.mana_cost = ManaCost.parse("{2}")
        so = self._push_spell_to_stack(game, p2, enemy_spell)

        sculpt = ManaSculpt(owner=p1, controller=p1)
        sculpt.chosen_targets = [so]
        sculpt.on_resolve(game)

        game.active_player_index = 0
        from engine.events import BeginningOfUpkeepTriggeredEvent
        # Fire twice
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        while game.stack._items:
            top = game.stack._items.pop()
            top.on_resolve(game)
        mana_first = p1.mana_pool.get(ManaType.COLORLESS)

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        while game.stack._items:
            top = game.stack._items.pop()
            top.on_resolve(game)
        mana_second = p1.mana_pool.get(ManaType.COLORLESS)

        # Second fire should not add more mana (trigger was unregistered)
        assert mana_second == mana_first
