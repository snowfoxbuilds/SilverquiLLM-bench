"""Audited tests for FDN 197 — Firespitter Whelp."""
from __future__ import annotations
from card_impl import FirespitterWhelp
from engine.card import CardImpl, Creature
from engine.types import CardType, Keyword, ManaCost
from test_utils import create_game
from engine.events import SpellCastTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestFirespitterWhelpBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = FirespitterWhelp(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = FirespitterWhelp(owner=None)
        assert card.name == 'Firespitter Whelp'

    def test_mana_cost(self) -> None:
        card = FirespitterWhelp(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{R}')

    def test_power_toughness(self) -> None:
        card = FirespitterWhelp(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_flying(self) -> None:
        card = FirespitterWhelp(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = FirespitterWhelp(owner=None)
        assert 'Dragon' in card.subtypes

class TestFirespitterWhelpTrigger:
    """Whenever you cast a noncreature or Dragon spell, deals 1 to each opponent."""

    def test_triggers_on_noncreature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        whelp = FirespitterWhelp(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whelp)
        whelp.register_triggers(game)
        noncreature = CardImpl(name='Bolt', mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        noncreature.card_types = {CardType.INSTANT}
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, spell=noncreature))
        _resolve_stack(game)
        assert p2.life == p2_life_before - 1

    def test_triggers_on_dragon_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        whelp = FirespitterWhelp(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whelp)
        whelp.register_triggers(game)
        dragon = Creature(name='Dragon', base_power=4, base_toughness=4, owner=p1, controller=p1, subtypes={'Dragon'})
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, spell=dragon))
        _resolve_stack(game)
        assert p2.life == p2_life_before - 1

    def test_does_not_trigger_on_non_dragon_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        whelp = FirespitterWhelp(owner=p1, controller=p1)
        game.get_battlefield(p1).add(whelp)
        whelp.register_triggers(game)
        bear = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1, subtypes={'Bear'})
        p2_life_before = p2.life
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, spell=bear))
        _resolve_stack(game)
        assert p2.life == p2_life_before
