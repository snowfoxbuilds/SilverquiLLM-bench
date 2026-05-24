"""Audited tests for FDN 47 — Mischievous Mystic."""
from __future__ import annotations
from card_impl import MischievousMystic
from engine.card import Creature
from engine.events import DrawsCardTriggeredEvent
from engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game

def _fire_and_resolve(game, event):
    game.trigger_manager.fire_event(game, event)
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestMischievousMysticBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = MischievousMystic(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = MischievousMystic(owner=None)
        assert card.name == 'Mischievous Mystic'

    def test_mana_cost(self) -> None:
        card = MischievousMystic(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{U}')

    def test_power_toughness(self) -> None:
        card = MischievousMystic(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_has_flying(self) -> None:
        card = MischievousMystic(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = MischievousMystic(owner=None)
        assert 'Human' in card.subtypes
        assert 'Wizard' in card.subtypes

class TestMischievousMysticTrigger:
    """Second draw each turn creates a 1/1 Faerie token with flying."""

    def test_first_draw_no_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MischievousMystic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        bf_others = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_others) == 0

    def test_second_draw_creates_faerie_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MischievousMystic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        bf_others = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_others) == 1

    def test_faerie_token_is_1_1_with_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MischievousMystic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        bf_others = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        token = bf_others[0]
        assert token.base_power == 1
        assert token.base_toughness == 1
        assert Keyword.FLYING in token.keywords

    def test_third_draw_no_extra_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MischievousMystic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        for _ in range(3):
            _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        bf_others = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_others) == 1

    def test_new_turn_resets(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MischievousMystic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        game.turn_number = 2
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p1))
        bf_others = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_others) == 2

    def test_opponent_draw_no_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MischievousMystic(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        game.turn_number = 1
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p2))
        _fire_and_resolve(game, DrawsCardTriggeredEvent(player=p2))
        bf_others = [c for c in game.get_battlefield(p1).get_all() if c is not card]
        assert len(bf_others) == 0
