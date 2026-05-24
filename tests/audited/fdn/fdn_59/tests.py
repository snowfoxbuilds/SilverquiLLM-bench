"""Audited tests for FDN 59 — Crypt Feaster."""
from __future__ import annotations
from card_impl import CryptFeaster
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import AttacksTriggeredEvent

class TestCryptFeasterBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = CryptFeaster(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CryptFeaster(owner=None)
        assert card.name == 'Crypt Feaster'

    def test_mana_cost(self) -> None:
        card = CryptFeaster(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{B}')

    def test_power_toughness(self) -> None:
        card = CryptFeaster(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_menace(self) -> None:
        card = CryptFeaster(owner=None)
        assert Keyword.MENACE in card.keywords

    def test_subtypes(self) -> None:
        card = CryptFeaster(owner=None)
        assert 'Zombie' in card.subtypes

class TestCryptFeasterThreshold:
    """Threshold attack trigger: +2/+0 if 7+ cards in graveyard."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_no_boost_below_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CryptFeaster(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        for i in range(6):
            c = Creature(name=f'GY{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        effects = game.effect_manager.get_all() if hasattr(game.effect_manager, 'get_all') else []
        source_effects = [e for e in effects if getattr(e, 'source', None) is card]
        assert len(source_effects) == 0

    def test_boost_at_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CryptFeaster(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        for i in range(7):
            c = Creature(name=f'GY{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        effects = game.effect_manager.get_all() if hasattr(game.effect_manager, 'get_all') else []
        source_effects = [e for e in effects if getattr(e, 'source', None) is card]
        assert len(source_effects) >= 1

    def test_does_not_trigger_for_other_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = CryptFeaster(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        for i in range(7):
            c = Creature(name=f'GY{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        other = Creature(name='Other', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=other))
        self._resolve_stack(game)
        effects = game.effect_manager.get_all() if hasattr(game.effect_manager, 'get_all') else []
        source_effects = [e for e in effects if getattr(e, 'source', None) is card]
        assert len(source_effects) == 0
