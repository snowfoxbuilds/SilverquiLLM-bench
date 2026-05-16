"""Audited tests for FDN 122 — Kykar, Zephyr Awakener."""
from __future__ import annotations
from card_impl import KykarZephyrAwakener
from engine.card import CardImpl, Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from tests.test_utils import create_game
from engine.events import SpellCastTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestKykarBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = KykarZephyrAwakener(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = KykarZephyrAwakener(owner=None)
        assert card.name == 'Kykar, Zephyr Awakener'

    def test_mana_cost(self) -> None:
        card = KykarZephyrAwakener(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{W}{U}')

    def test_power_toughness(self) -> None:
        card = KykarZephyrAwakener(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_is_legendary(self) -> None:
        card = KykarZephyrAwakener(owner=None)
        assert 'Legendary' in getattr(card, 'supertypes', set())

    def test_has_flying(self) -> None:
        card = KykarZephyrAwakener(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = KykarZephyrAwakener(owner=None)
        assert 'Bird' in card.subtypes
        assert 'Wizard' in card.subtypes

class TestKykarSpellTrigger:
    """Noncreature spell cast trigger."""

    def test_creates_spirit_token_on_noncreature_spell(self) -> None:
        """When choosing token mode, creates 1/1 Spirit with flying."""
        game = create_game()
        p1 = game.players[0]
        kykar = KykarZephyrAwakener(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kykar)
        kykar.register_triggers(game)
        spell = CardImpl(name='Lightning Bolt')
        spell.card_types = {CardType.INSTANT}
        spell.controller = p1
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=spell, card=spell, player=p1))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        spirits = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Spirit']
        assert len(spirits) == 1
        assert spirits[0].base_power == 1
        assert spirits[0].base_toughness == 1
        assert Keyword.FLYING in spirits[0].keywords

    def test_no_trigger_on_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kykar = KykarZephyrAwakener(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kykar)
        kykar.register_triggers(game)
        creature_spell = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1)
        creature_spell.controller = p1
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=creature_spell, card=creature_spell, player=p1))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        spirits = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Spirit']
        assert len(spirits) == 0

    def test_flicker_mode_exiles_creature(self) -> None:
        """When choosing flicker mode, exiles another creature."""
        game = create_game()
        p1 = game.players[0]
        kykar = KykarZephyrAwakener(owner=p1, controller=p1)
        ally = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(kykar)
        game.get_battlefield(p1).add(ally)
        kykar.register_triggers(game)
        p1._script.appendleft(ally)
        p1._script.appendleft('flicker')
        spell = CardImpl(name='Opt')
        spell.card_types = {CardType.INSTANT}
        spell.controller = p1
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=spell, card=spell, player=p1))
        _resolve_stack(game)
        assert p1.zones[Zone.EXILE].contains(ally)

    def test_no_trigger_on_opponent_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        kykar = KykarZephyrAwakener(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kykar)
        kykar.register_triggers(game)
        spell = CardImpl(name='Shock')
        spell.card_types = {CardType.INSTANT}
        spell.controller = p2
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(spell=spell, card=spell, player=p2))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        spirits = [c for c in bf.get_all() if getattr(c, 'name', '') == 'Spirit']
        assert len(spirits) == 0
