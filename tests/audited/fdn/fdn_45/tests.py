"""Audited tests for FDN 45 — Kiora, the Rising Tide."""
from __future__ import annotations
from card_impl import KioraTheRisingTide
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game

class TestKioraBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = KioraTheRisingTide(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = KioraTheRisingTide(owner=None)
        assert card.name == 'Kiora, the Rising Tide'

    def test_mana_cost(self) -> None:
        card = KioraTheRisingTide(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{U}')

    def test_power_toughness(self) -> None:
        card = KioraTheRisingTide(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_legendary(self) -> None:
        card = KioraTheRisingTide(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = KioraTheRisingTide(owner=None)
        assert 'Merfolk' in card.subtypes
        assert 'Noble' in card.subtypes

class TestKioraETB:
    """ETB: draw 2, discard 2."""

    def test_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KioraTheRisingTide(owner=p1, controller=p1)
        for i in range(5):
            c = Creature(name=f'Lib{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        card.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 0

    def test_discards_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KioraTheRisingTide(owner=p1, controller=p1)
        for i in range(5):
            c = Creature(name=f'Lib{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card.on_resolve(game)
        gy_cards = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy_cards) == 2

    def test_etb_with_empty_library(self) -> None:
        """If library is empty, no draws and no crash."""
        game = create_game()
        p1 = game.players[0]
        card = KioraTheRisingTide(owner=p1, controller=p1)
        card.on_resolve(game)

class TestKioraThreshold:
    """Threshold: attack with 7+ cards in graveyard creates 8/8 token."""

    def _fire_and_resolve(self, game, event):
        game.trigger_manager.fire_event(game, event)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_attack_with_threshold_creates_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KioraTheRisingTide(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        for i in range(7):
            c = Creature(name=f'Dead{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        p1._script.append(True)
        card.register_triggers(game)
        self._fire_and_resolve(game, AttacksTriggeredEvent(creature=card))
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Scion of the Deep']
        assert len(tokens) == 1

    def test_scion_is_8_8_legendary(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KioraTheRisingTide(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        for i in range(7):
            c = Creature(name=f'Dead{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        p1._script.append(True)
        card.register_triggers(game)
        self._fire_and_resolve(game, AttacksTriggeredEvent(creature=card))
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Scion of the Deep']
        token = tokens[0]
        assert token.base_power == 8
        assert token.base_toughness == 8
        assert Supertype.LEGENDARY in token.supertypes

    def test_attack_below_threshold_no_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KioraTheRisingTide(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        for i in range(6):
            c = Creature(name=f'Dead{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        card.register_triggers(game)
        self._fire_and_resolve(game, AttacksTriggeredEvent(creature=card))
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Scion of the Deep']
        assert len(tokens) == 0

    def test_may_decline_token_creation(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = KioraTheRisingTide(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        for i in range(7):
            c = Creature(name=f'Dead{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        p1._script.append(False)
        card.register_triggers(game)
        self._fire_and_resolve(game, AttacksTriggeredEvent(creature=card))
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Scion of the Deep']
        assert len(tokens) == 0
