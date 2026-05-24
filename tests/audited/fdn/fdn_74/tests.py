"""Audited tests for FDN 74 — Vampire Gourmand."""
from __future__ import annotations
from card_impl import VampireGourmand
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent

class TestVampireGourmandBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = VampireGourmand(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = VampireGourmand(owner=None)
        assert card.name == 'Vampire Gourmand'

    def test_mana_cost(self) -> None:
        card = VampireGourmand(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{B}')

    def test_power_toughness(self) -> None:
        card = VampireGourmand(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = VampireGourmand(owner=None)
        assert 'Vampire' in card.subtypes

class TestVampireGourmandAttackTrigger:
    """Whenever attacks, may sacrifice another creature for draw + unblockable."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_sacrifice_draws_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VampireGourmand(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        fodder = Creature(name='Fodder', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)
        card.register_triggers(game)
        lib_card = Creature(name='Lib', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before + 1

    def test_sacrificed_creature_leaves_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VampireGourmand(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        fodder = Creature(name='Fodder', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)
        card.register_triggers(game)
        lib_card = Creature(name='Lib', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert not game.get_battlefield(p1).contains(fodder)

    def test_no_sacrifice_with_no_other_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VampireGourmand(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        hand_after = len(p1.zones[Zone.HAND].get_all())
        assert hand_after == hand_before

    def test_cant_be_blocked_after_sacrifice(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = VampireGourmand(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        fodder = Creature(name='Fodder', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(fodder)
        card.register_triggers(game)
        lib_card = Creature(name='Lib', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=card))
        self._resolve_stack(game)
        assert getattr(card, '_cant_be_blocked', False) is True
