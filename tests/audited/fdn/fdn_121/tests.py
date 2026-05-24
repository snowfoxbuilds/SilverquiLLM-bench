"""Audited tests for FDN 121 — Koma, World-Eater."""
from __future__ import annotations
from card_impl import KomaWorldEater
from engine.card import Creature
from engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from engine.events import DealsDamageTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestKomaBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = KomaWorldEater(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = KomaWorldEater(owner=None)
        assert card.name == 'Koma, World-Eater'

    def test_mana_cost(self) -> None:
        card = KomaWorldEater(owner=None)
        assert card.mana_cost == ManaCost.parse('{3}{G}{G}{U}{U}')

    def test_power_toughness(self) -> None:
        card = KomaWorldEater(owner=None)
        assert card.base_power == 8
        assert card.base_toughness == 12

    def test_is_legendary(self) -> None:
        card = KomaWorldEater(owner=None)
        assert 'Legendary' in getattr(card, 'supertypes', set())

    def test_has_trample(self) -> None:
        card = KomaWorldEater(owner=None)
        assert Keyword.TRAMPLE in card.keywords

    def test_has_ward(self) -> None:
        card = KomaWorldEater(owner=None)
        assert Keyword.WARD in card.keywords

    def test_subtypes(self) -> None:
        card = KomaWorldEater(owner=None)
        assert 'Serpent' in card.subtypes

    def test_cant_be_countered_flag(self) -> None:
        card = KomaWorldEater(owner=None)
        assert getattr(card, '_cant_be_countered', False) is True

class TestKomaCombatDamage:
    """Combat damage trigger: create four 3/3 Serpent tokens."""

    def test_creates_four_tokens_on_combat_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        koma = KomaWorldEater(owner=p1, controller=p1)
        game.get_battlefield(p1).add(koma)
        koma.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=koma, target=p2, amount=8, is_combat=True))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'name', '') == "Koma's Coil"]
        assert len(tokens) == 4

    def test_tokens_are_3_3_serpents(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        koma = KomaWorldEater(owner=p1, controller=p1)
        game.get_battlefield(p1).add(koma)
        koma.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=koma, target=p2, amount=8, is_combat=True))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'name', '') == "Koma's Coil"]
        for token in tokens:
            assert token.base_power == 3
            assert token.base_toughness == 3
            assert 'Serpent' in token.subtypes

    def test_no_trigger_on_damage_to_creature(self) -> None:
        """Only triggers when dealing combat damage to a player."""
        game = create_game()
        p1 = game.players[0]
        koma = KomaWorldEater(owner=p1, controller=p1)
        game.get_battlefield(p1).add(koma)
        target_creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=game.players[1])
        koma.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=koma, target=target_creature, amount=8))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'name', '') == "Koma's Coil"]
        assert len(tokens) == 0
