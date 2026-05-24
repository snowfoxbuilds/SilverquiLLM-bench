"""Audited tests for FDN 93 — Searslicer Goblin."""
from __future__ import annotations
from card_impl import SearslicerGoblin
from engine.card import Creature
from engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import EndStepTriggeredEvent

class TestSearslicerGoblinBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SearslicerGoblin(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SearslicerGoblin(owner=None)
        assert card.name == 'Searslicer Goblin'

    def test_mana_cost(self) -> None:
        card = SearslicerGoblin(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{R}')

    def test_power_toughness(self) -> None:
        card = SearslicerGoblin(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = SearslicerGoblin(owner=None)
        assert 'Goblin' in card.subtypes
        assert 'Warrior' in card.subtypes

class TestSearslicerGoblinRaidTrigger:
    """Raid — end step: create 1/1 Goblin token if attacked this turn."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_creates_token_when_attacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        card = SearslicerGoblin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.attacked_this_turn = True
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        self._resolve_stack(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        assert bf_after == bf_before + 1

    def test_no_token_when_not_attacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        card = SearslicerGoblin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.attacked_this_turn = False
        p1.attacked_this_turn = False
        bf_before = len(list(game.get_battlefield(p1).get_all()))
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        self._resolve_stack(game)
        bf_after = len(list(game.get_battlefield(p1).get_all()))
        assert bf_after == bf_before

    def test_token_is_goblin(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        card = SearslicerGoblin(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.attacked_this_turn = True
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent())
        self._resolve_stack(game)
        bf = list(game.get_battlefield(p1).get_all())
        tokens = [c for c in bf if c is not card]
        assert len(tokens) == 1
        assert 'Goblin' in getattr(tokens[0], 'subtypes', set())
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1
