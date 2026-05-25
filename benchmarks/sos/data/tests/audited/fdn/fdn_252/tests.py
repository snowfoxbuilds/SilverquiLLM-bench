"""Audited tests for FDN 252 — Gleaming Barrier."""
from __future__ import annotations
from card_impl import GleamingBarrier
from engine.card import ArtifactCreature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game
from engine.events import CreatureDiesTriggeredEvent

class TestGleamingBarrierBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = GleamingBarrier(owner=None)
        assert card.name == 'Gleaming Barrier'

    def test_mana_cost(self) -> None:
        card = GleamingBarrier(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}')

    def test_power_toughness(self) -> None:
        card = GleamingBarrier(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 4

    def test_is_artifact_creature(self) -> None:
        card = GleamingBarrier(owner=None)
        assert isinstance(card, ArtifactCreature)

    def test_wall_subtype(self) -> None:
        card = GleamingBarrier(owner=None)
        assert 'Wall' in card.subtypes

    def test_has_defender(self) -> None:
        card = GleamingBarrier(owner=None)
        assert Keyword.DEFENDER & card.keywords

class TestGleamingBarrierDeathTrigger:
    """When this creature dies, create a Treasure token."""

    def test_creates_treasure_on_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        barrier = GleamingBarrier(owner=p1, controller=p1)
        game.get_battlefield(p1).add(barrier)
        barrier.register_triggers(game)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=barrier))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        treasures = [c for c in bf if getattr(c, 'name', '') == 'Treasure']
        assert len(treasures) >= 1

    def test_treasure_is_artifact(self) -> None:
        game = create_game()
        p1 = game.players[0]
        barrier = GleamingBarrier(owner=p1, controller=p1)
        game.get_battlefield(p1).add(barrier)
        barrier.register_triggers(game)
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=barrier))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        treasures = [c for c in bf if getattr(c, 'name', '') == 'Treasure']
        assert len(treasures) >= 1
        assert CardType.ARTIFACT in treasures[0].card_types

    def test_no_treasure_for_other_creature_death(self) -> None:
        game = create_game()
        p1 = game.players[0]
        barrier = GleamingBarrier(owner=p1, controller=p1)
        game.get_battlefield(p1).add(barrier)
        barrier.register_triggers(game)
        from engine.card import Creature
        other = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        bf_before = len(game.get_battlefield(p1).get_all())
        game.trigger_manager.fire_event(game, CreatureDiesTriggeredEvent(creature=other))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after == bf_before
