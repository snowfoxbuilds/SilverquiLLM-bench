"""Audited tests for FDN 78 — Battlesong Berserker."""
from __future__ import annotations
from card_impl import BattlesongBerserker
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import AttacksTriggeredEvent

class TestBattlesongBerserkerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = BattlesongBerserker(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BattlesongBerserker(owner=None)
        assert card.name == 'Battlesong Berserker'

    def test_mana_cost(self) -> None:
        card = BattlesongBerserker(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{R}')

    def test_power_toughness(self) -> None:
        card = BattlesongBerserker(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = BattlesongBerserker(owner=None)
        assert 'Human' in card.subtypes
        assert 'Berserker' in card.subtypes

class TestBattlesongBerserkerAttackTrigger:
    """Whenever you attack, target creature gets +1/+0 and menace until EOT."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        game.effect_manager.apply_all(game)

    def test_target_creature_gets_power_boost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BattlesongBerserker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        target = Creature(name='Target', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.register_triggers(game)
        p1._script.appendleft(target)
        power_before = target.base_power
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert target.modified_power == power_before + 1

    def test_target_creature_gains_menace(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BattlesongBerserker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        target = Creature(name='Target', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(target)
        card.register_triggers(game)
        p1._script.appendleft(target)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        kw = getattr(target, 'keywords', Keyword(0)) or Keyword(0)
        assert kw & Keyword.MENACE

    def test_can_target_self(self) -> None:
        """Berserker can target itself with the attack trigger."""
        game = create_game()
        p1 = game.players[0]
        card = BattlesongBerserker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        p1._script.appendleft(card)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert card.modified_power == power_before + 1

    def test_does_not_trigger_for_opponent_attack(self) -> None:
        """Trigger only fires when controller's creature attacks."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = BattlesongBerserker(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        enemy = Creature(name='Enemy', base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(enemy)
        power_before = card.base_power
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=enemy))
        self._resolve_stack(game)
        assert card.base_power == power_before
