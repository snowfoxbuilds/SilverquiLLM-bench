"""Audited tests for FDN 107 — Mossborn Hydra."""
from __future__ import annotations
from card_impl import MossbornHydra
from engine.card import Creature, Land
from engine.types import CardType, Keyword, ManaCost
from tests.test_utils import create_game
from engine.events import EntersBattlefieldTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestMossbornHydraBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = MossbornHydra(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = MossbornHydra(owner=None)
        assert card.name == 'Mossborn Hydra'

    def test_mana_cost(self) -> None:
        card = MossbornHydra(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{G}')

    def test_base_power_toughness(self) -> None:
        card = MossbornHydra(owner=None)
        assert card.base_power == 0
        assert card.base_toughness == 0

    def test_has_trample(self) -> None:
        card = MossbornHydra(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_subtypes(self) -> None:
        card = MossbornHydra(owner=None)
        assert 'Elemental' in card.subtypes
        assert 'Hydra' in card.subtypes

class TestMossbornHydraETB:
    """Enters with a +1/+1 counter."""

    def test_on_resolve_adds_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hydra = MossbornHydra(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hydra)
        hydra.on_resolve(game)
        assert hydra.plus_one_counters == 1
        assert hydra._original_plus_one_counters == 1

    def test_power_toughness_with_counter(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hydra = MossbornHydra(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hydra)
        hydra.on_resolve(game)
        assert hydra.power == 1
        assert hydra.toughness == 1

class TestMossbornHydraLandfall:
    """Landfall: double +1/+1 counters."""

    def test_landfall_doubles_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hydra = MossbornHydra(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hydra)
        hydra.on_resolve(game)
        hydra.register_triggers(game)
        land = Land(name='Forest', owner=p1, controller=p1)
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        assert hydra.plus_one_counters == 2
        assert hydra._original_plus_one_counters == 2

    def test_landfall_doubles_again(self) -> None:
        """Two lands = double twice: 1 -> 2 -> 4."""
        game = create_game()
        p1 = game.players[0]
        hydra = MossbornHydra(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hydra)
        hydra.on_resolve(game)
        hydra.register_triggers(game)
        for i in range(2):
            land = Land(name=f'Forest{i}', owner=p1, controller=p1)
            game.get_battlefield(p1).add(land)
            game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
            _resolve_stack(game)
        assert hydra.plus_one_counters == 4

    def test_landfall_zero_counters_stays_zero(self) -> None:
        """If somehow has 0 counters, doubling keeps 0."""
        game = create_game()
        p1 = game.players[0]
        hydra = MossbornHydra(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hydra)
        hydra.register_triggers(game)
        land = Land(name='Forest', owner=p1, controller=p1)
        game.get_battlefield(p1).add(land)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=land))
        _resolve_stack(game)
        assert hydra.plus_one_counters == 0
