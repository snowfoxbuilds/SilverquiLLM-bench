"""Audited tests for FDN 58 — Bloodthirsty Conqueror."""
from __future__ import annotations
from card_impl import BloodthirstyConqueror
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import LosesLifeTriggeredEvent

class TestBloodthirstyConquerorBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = BloodthirstyConqueror(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BloodthirstyConqueror(owner=None)
        assert card.name == 'Bloodthirsty Conqueror'

    def test_mana_cost(self) -> None:
        card = BloodthirstyConqueror(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{B}{B}')

    def test_power_toughness(self) -> None:
        card = BloodthirstyConqueror(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying_and_deathtouch(self) -> None:
        card = BloodthirstyConqueror(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_subtypes(self) -> None:
        card = BloodthirstyConqueror(owner=None)
        assert 'Vampire' in card.subtypes
        assert 'Knight' in card.subtypes

class TestBloodthirstyConquerorTrigger:
    """Whenever an opponent loses life, you gain that much life."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_gains_life_when_opponent_loses(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = BloodthirstyConqueror(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        life_before = p1.life
        game.trigger_manager.fire_event(game, LosesLifeTriggeredEvent(player=p2, amount=3))
        self._resolve_stack(game)
        assert p1.life == life_before + 3

    def test_no_trigger_when_self_loses_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BloodthirstyConqueror(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        life_before = p1.life
        game.trigger_manager.fire_event(game, LosesLifeTriggeredEvent(player=p1, amount=3))
        self._resolve_stack(game)
        assert p1.life == life_before

    def test_no_trigger_with_zero_amount(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = BloodthirstyConqueror(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)
        life_before = p1.life
        game.trigger_manager.fire_event(game, LosesLifeTriggeredEvent(player=p2, amount=0))
        self._resolve_stack(game)
        assert p1.life == life_before
