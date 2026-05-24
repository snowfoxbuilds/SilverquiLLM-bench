"""Audited tests for FDN 39 — Grappling Kraken."""
from __future__ import annotations
from card_impl import GrapplingKraken
from engine.card import Creature
from engine.types import CardType, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

class TestGrapplingKrakenBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = GrapplingKraken(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GrapplingKraken(owner=None)
        assert card.name == 'Grappling Kraken'

    def test_mana_cost(self) -> None:
        card = GrapplingKraken(owner=None)
        assert card.mana_cost == ManaCost.parse('{4}{U}{U}')

    def test_power_toughness(self) -> None:
        card = GrapplingKraken(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 6

    def test_subtypes(self) -> None:
        card = GrapplingKraken(owner=None)
        assert 'Kraken' in card.subtypes

class TestGrapplingKrakenLandfall:
    """Landfall — tap target opponent creature and put stun counter on it."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        kraken = GrapplingKraken(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kraken)
        enemy = Creature(name='Enemy', base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(enemy)
        kraken.register_triggers(game)
        return (game, kraken, p1, p2, enemy)

    def _make_land(self, owner):
        """Create a minimal land-like object."""
        from engine.card import CardImpl
        land = CardImpl(name='Island', owner=owner, controller=owner)
        land.card_types = {CardType.LAND}
        return land

    def test_taps_opponent_creature_on_landfall(self) -> None:
        game, kraken, p1, p2, enemy = self._setup()
        land = self._make_land(p1)
        land.controller = p1
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land, controller=p1))
        self._resolve_stack(game)
        assert enemy.tapped is True

    def test_adds_stun_counter_on_landfall(self) -> None:
        game, kraken, p1, p2, enemy = self._setup()
        land = self._make_land(p1)
        land.controller = p1
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land, controller=p1))
        self._resolve_stack(game)
        assert getattr(enemy, 'stun_counters', 0) >= 1

    def test_no_trigger_on_opponent_land(self) -> None:
        game, kraken, p1, p2, enemy = self._setup()
        land = self._make_land(p2)
        land.controller = p2
        game.get_battlefield(p2).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land, controller=p2))
        self._resolve_stack(game)
        assert not getattr(enemy, 'tapped', False)

    def test_no_trigger_on_non_land_entering(self) -> None:
        game, kraken, p1, p2, enemy = self._setup()
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=creature, controller=p1))
        self._resolve_stack(game)
        assert not getattr(enemy, 'tapped', False)
