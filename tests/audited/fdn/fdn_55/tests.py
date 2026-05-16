"""Audited tests for FDN 55 — Arbiter of Woe."""
from __future__ import annotations
from card_impl import ArbiterOfWoe
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

class TestArbiterOfWoeBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ArbiterOfWoe(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ArbiterOfWoe(owner=None)
        assert card.name == 'Arbiter of Woe'

    def test_mana_cost(self) -> None:
        card = ArbiterOfWoe(owner=None)
        assert card.mana_cost == ManaCost.parse('{4}{B}{B}')

    def test_power_toughness(self) -> None:
        card = ArbiterOfWoe(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = ArbiterOfWoe(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = ArbiterOfWoe(owner=None)
        assert 'Demon' in card.subtypes

class TestArbiterOfWoeETB:
    """ETB: each opponent discards a card and loses 2 life; you draw and gain 2."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_opponent_loses_2_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ArbiterOfWoe(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        filler = Creature(name='Filler', base_power=1, base_toughness=1, owner=p2)
        p2.zones[Zone.HAND].add(filler)
        life_before = p2.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=card))
        self._resolve_stack(game)
        assert p2.life == life_before - 2

    def test_controller_gains_2_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ArbiterOfWoe(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        filler = Creature(name='Filler', base_power=1, base_toughness=1, owner=p2)
        p2.zones[Zone.HAND].add(filler)
        lib_card = Creature(name='Lib', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        life_before = p1.life
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=card))
        self._resolve_stack(game)
        assert p1.life == life_before + 2

    def test_controller_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ArbiterOfWoe(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        filler = Creature(name='Filler', base_power=1, base_toughness=1, owner=p2)
        p2.zones[Zone.HAND].add(filler)
        lib_card = Creature(name='Lib', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=card))
        self._resolve_stack(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before + 1

    def test_opponent_discards_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ArbiterOfWoe(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        filler = Creature(name='Filler', base_power=1, base_toughness=1, owner=p2)
        p2.zones[Zone.HAND].add(filler)
        lib_card = Creature(name='Lib', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=card))
        self._resolve_stack(game)
        hand_after = len(p2.zones[Zone.HAND].get_all())
        assert hand_after == 0
