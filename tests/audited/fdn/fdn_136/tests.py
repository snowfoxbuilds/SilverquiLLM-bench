"""Audited tests for FDN 136 — Angel of Finality."""
from __future__ import annotations
from card_impl import AngelOfFinality
from engine.card import CardImpl, Creature
from engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestAngelOfFinalityBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = AngelOfFinality(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AngelOfFinality(owner=None)
        assert card.name == 'Angel of Finality'

    def test_mana_cost(self) -> None:
        card = AngelOfFinality(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{W}')

    def test_power_toughness(self) -> None:
        card = AngelOfFinality(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_flying(self) -> None:
        card = AngelOfFinality(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_angel_subtype(self) -> None:
        card = AngelOfFinality(owner=None)
        assert 'Angel' in card.subtypes

class TestAngelOfFinalityETB:
    """When this creature enters, exile target player's graveyard."""

    def test_exiles_opponent_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        angel = AngelOfFinality(owner=p1, controller=p1)
        gy_card1 = CardImpl(name='Bear', owner=p2)
        gy_card2 = CardImpl(name='Elk', owner=p2)
        p2.zones[Zone.GRAVEYARD].add(gy_card1)
        p2.zones[Zone.GRAVEYARD].add(gy_card2)
        game.get_battlefield(p1).add(angel)
        angel.register_triggers(game)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=angel))
        _resolve_stack(game)
        assert len(list(p2.zones[Zone.GRAVEYARD].get_all())) == 0

    def test_exiled_cards_go_to_exile(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        angel = AngelOfFinality(owner=p1, controller=p1)
        gy_card = CardImpl(name='Bear', owner=p2)
        p2.zones[Zone.GRAVEYARD].add(gy_card)
        game.get_battlefield(p1).add(angel)
        angel.register_triggers(game)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=angel))
        _resolve_stack(game)
        exile_cards = list(p2.zones[Zone.EXILE].get_all())
        assert any((c.name == 'Bear' for c in exile_cards))
