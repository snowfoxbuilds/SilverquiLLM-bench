"""Audited tests for FDN 118 — Dreadwing Scavenger."""
from __future__ import annotations
from card_impl import DreadwingScavenger
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from test_utils import create_game
from engine.events import AttacksTriggeredEvent

def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestDreadwingScavengerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = DreadwingScavenger(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = DreadwingScavenger(owner=None)
        assert card.name == 'Dreadwing Scavenger'

    def test_mana_cost(self) -> None:
        card = DreadwingScavenger(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{U}{B}')

    def test_power_toughness(self) -> None:
        card = DreadwingScavenger(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_flying(self) -> None:
        card = DreadwingScavenger(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = DreadwingScavenger(owner=None)
        assert 'Nightmare' in card.subtypes
        assert 'Bird' in card.subtypes

class TestDreadwingScavengerLoot:
    """ETB and attack trigger: draw then discard."""

    def test_etb_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scav = DreadwingScavenger(owner=p1, controller=p1)
        filler = Creature(name='Filler', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(filler)
        hand_card = Creature(name='HandCard', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.HAND].add(hand_card)
        p1._script.appendleft(hand_card)
        scav.on_resolve(game)
        assert p1.zones[Zone.GRAVEYARD].contains(hand_card)

    def test_attack_loots(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scav = DreadwingScavenger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scav)
        filler = Creature(name='Filler', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(filler)
        hand_card = Creature(name='HandCard', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.HAND].add(hand_card)
        scav.register_triggers(game)
        p1._script.appendleft(hand_card)
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=scav))
        _resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(hand_card)

class TestDreadwingScavengerThreshold:
    """Threshold: +1/+1 and deathtouch with 7+ cards in graveyard."""

    def test_threshold_active_with_seven_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scav = DreadwingScavenger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scav)
        for i in range(7):
            c = Creature(name=f'Dead{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        scav.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert scav.modified_power >= 3
        assert scav.modified_toughness >= 3
        assert Keyword.DEATHTOUCH in scav.keywords

    def test_threshold_inactive_with_fewer_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        scav = DreadwingScavenger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(scav)
        for i in range(3):
            c = Creature(name=f'Dead{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        scav.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert scav.base_power == 2
        assert scav.base_toughness == 2
