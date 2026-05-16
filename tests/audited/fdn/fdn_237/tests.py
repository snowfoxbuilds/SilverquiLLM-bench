"""Audited tests for FDN 237 — Balmor, Battlemage Captain."""
from __future__ import annotations
from card_impl import BalmorBattlemageCaptain
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype
from tests.test_utils import create_game
from engine.events import SpellCastTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestBalmorBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = BalmorBattlemageCaptain(owner=None)
        assert card.name == 'Balmor, Battlemage Captain'

    def test_mana_cost(self) -> None:
        card = BalmorBattlemageCaptain(owner=None)
        assert card.mana_cost == ManaCost.parse('{U}{R}')

    def test_power_toughness(self) -> None:
        card = BalmorBattlemageCaptain(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        card = BalmorBattlemageCaptain(owner=None)
        assert Keyword.FLYING & card.keywords

    def test_is_legendary(self) -> None:
        card = BalmorBattlemageCaptain(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = BalmorBattlemageCaptain(owner=None)
        assert 'Bird' in card.subtypes
        assert 'Wizard' in card.subtypes

class TestBalmorTrigger:
    """Instant/sorcery cast gives creatures +1/+0 and trample."""

    def test_instant_cast_buffs_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        balmor = BalmorBattlemageCaptain(owner=p1, controller=p1)
        game.get_battlefield(p1).add(balmor)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        balmor.register_triggers(game)
        spell = Instant(name='Bolt', owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, card=spell))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert other.base_power == 3

    def test_instant_cast_grants_trample(self) -> None:
        game = create_game()
        p1 = game.players[0]
        balmor = BalmorBattlemageCaptain(owner=p1, controller=p1)
        game.get_battlefield(p1).add(balmor)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        balmor.register_triggers(game)
        spell = Instant(name='Bolt', owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, card=spell))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert Keyword.TRAMPLE & other.keywords

    def test_opponent_spell_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        balmor = BalmorBattlemageCaptain(owner=p1, controller=p1)
        game.get_battlefield(p1).add(balmor)
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        balmor.register_triggers(game)
        spell = Instant(name='Bolt', owner=p2, controller=p2)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p2, card=spell))
        _resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert other.base_power == 2
