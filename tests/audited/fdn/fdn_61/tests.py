"""Audited tests for FDN 61 — High-Society Hunter."""
from __future__ import annotations
import pytest
from card_impl import HighSocietyHunter
from engine.card import Creature
from engine.events import AttacksTriggeredEvent, CreatureDiesTriggeredEvent
from engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game

class TestHighSocietyHunterBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = HighSocietyHunter(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = HighSocietyHunter(owner=None)
        assert card.name == 'High-Society Hunter'

    def test_mana_cost(self) -> None:
        card = HighSocietyHunter(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{B}{B}')

    def test_power_toughness(self) -> None:
        card = HighSocietyHunter(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = HighSocietyHunter(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes_vampire_noble(self) -> None:
        card = HighSocietyHunter(owner=None)
        assert 'Vampire' in card.subtypes
        assert 'Noble' in card.subtypes

class TestHighSocietyHunterAttackTrigger:
    """Attack trigger: may sacrifice another creature for +1/+1 counter."""

    def _setup_attack(self, *, sacrifice_choice=None):
        game = create_game()
        p1 = game.players[0]
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hunter)
        hunter.register_triggers(game)
        return (game, hunter, p1)

    def test_registers_attack_trigger(self) -> None:
        game, hunter, p1 = self._setup_attack()
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        attack_triggers = [t for t in triggers if t.event_type is AttacksTriggeredEvent]
        assert len(attack_triggers) >= 1

    def test_attack_trigger_condition_fires_for_self(self) -> None:
        game, hunter, p1 = self._setup_attack()
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is AttacksTriggeredEvent][0]
        assert reg.condition(game, AttacksTriggeredEvent(creature=hunter)) is True

    def test_attack_trigger_condition_does_not_fire_for_other(self) -> None:
        game, hunter, p1 = self._setup_attack()
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is AttacksTriggeredEvent][0]
        assert reg.condition(game, AttacksTriggeredEvent(creature=other)) is False

    def test_sacrifice_adds_plus_one_counter(self) -> None:
        """When attack trigger fires with a sacrifice target, add counter."""
        game = create_game()
        p1 = game.players[0]
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        fodder = Creature(name='Rat', base_power=1, base_toughness=1, owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hunter)
        bf.add(fodder)
        hunter.register_triggers(game)
        p1._script.append(fodder)
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is AttacksTriggeredEvent][0]
        reg.effect(game)
        assert hunter.plus_one_counters >= 1

    def test_no_sacrifice_target_no_counter(self) -> None:
        """If no other creature to sacrifice, no counter added."""
        game = create_game()
        p1 = game.players[0]
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hunter)
        hunter.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is AttacksTriggeredEvent][0]
        reg.effect(game)
        assert hunter.plus_one_counters == 0

    def test_decline_sacrifice_no_counter(self) -> None:
        """If player declines sacrifice (choose None), no counter added."""
        game = create_game()
        p1 = game.players[0]
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        fodder = Creature(name='Rat', base_power=1, base_toughness=1, owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hunter)
        bf.add(fodder)
        hunter.register_triggers(game)
        p1._script.append(None)
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is AttacksTriggeredEvent][0]
        reg.effect(game)
        assert hunter.plus_one_counters == 0

class TestHighSocietyHunterDeathTrigger:
    """Death trigger: another nontoken creature dies → draw a card."""

    def _setup_death(self):
        game = create_game()
        p1 = game.players[0]
        hunter = HighSocietyHunter(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hunter)
        hunter.register_triggers(game)
        return (game, hunter, p1)

    def test_registers_death_trigger(self) -> None:
        game, hunter, p1 = self._setup_death()
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        death_triggers = [t for t in triggers if t.event_type is CreatureDiesTriggeredEvent]
        assert len(death_triggers) >= 1

    def test_death_condition_fires_for_other_nontoken(self) -> None:
        game, hunter, p1 = self._setup_death()
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        other.is_token = False
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is CreatureDiesTriggeredEvent][0]
        assert reg.condition(game, CreatureDiesTriggeredEvent(creature=other)) is True

    def test_death_condition_does_not_fire_for_self(self) -> None:
        game, hunter, p1 = self._setup_death()
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is CreatureDiesTriggeredEvent][0]
        assert reg.condition(game, CreatureDiesTriggeredEvent(creature=hunter)) is False

    def test_death_condition_does_not_fire_for_token(self) -> None:
        game, hunter, p1 = self._setup_death()
        token = Creature(name='Token', base_power=1, base_toughness=1, owner=p1, controller=p1)
        token.is_token = True
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is CreatureDiesTriggeredEvent][0]
        assert reg.condition(game, CreatureDiesTriggeredEvent(creature=token)) is False

    def test_death_trigger_draws_card(self) -> None:
        """When death effect fires, controller draws a card."""
        from engine.card import CardImpl
        from engine.types import Zone
        game, hunter, p1 = self._setup_death()
        lib_card = CardImpl(name='Mountain', owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        hand_count_before = len(p1.zones[Zone.HAND].get_all())
        triggers = game.trigger_manager.get_triggers_for_source(hunter)
        reg = [t for t in triggers if t.event_type is CreatureDiesTriggeredEvent][0]
        reg.effect(game)
        hand_count_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_count_after == hand_count_before + 1
