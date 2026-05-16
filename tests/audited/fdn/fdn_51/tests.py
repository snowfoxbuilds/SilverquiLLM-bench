"""Audited tests for FDN 51 — Sphinx of Forgotten Lore."""
from __future__ import annotations
from card_impl import SphinxOfForgottenLore
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game

class TestSphinxOfForgottenLoreBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SphinxOfForgottenLore(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SphinxOfForgottenLore(owner=None)
        assert card.name == 'Sphinx of Forgotten Lore'

    def test_mana_cost(self) -> None:
        card = SphinxOfForgottenLore(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{U}{U}')

    def test_power_toughness(self) -> None:
        card = SphinxOfForgottenLore(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_has_flash(self) -> None:
        card = SphinxOfForgottenLore(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_has_flying(self) -> None:
        card = SphinxOfForgottenLore(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_sphinx_subtype(self) -> None:
        card = SphinxOfForgottenLore(owner=None)
        assert 'Sphinx' in card.subtypes

class TestSphinxAttackTrigger:
    """Attack trigger: grant flashback to instant/sorcery in graveyard."""

    def _fire_and_resolve(self, game, event_type, data):
        game.trigger_manager.fire_event(game, event_type, data)
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_attack_grants_flashback_to_chosen_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SphinxOfForgottenLore(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        bolt = Instant(name='Bolt', mana_cost=ManaCost.parse('{R}'), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(bolt)
        p1._script.append(bolt)
        card.register_triggers(game)
        self._fire_and_resolve(game, EventType.ATTACKS, {'attacker': card, 'creature': card})
        assert getattr(bolt, 'has_flashback', False) is True

    def test_flashback_cost_equals_mana_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SphinxOfForgottenLore(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        bolt = Instant(name='Bolt', mana_cost=ManaCost.parse('{R}'), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(bolt)
        p1._script.append(bolt)
        card.register_triggers(game)
        self._fire_and_resolve(game, EventType.ATTACKS, {'attacker': card, 'creature': card})
        assert bolt.flashback_cost == bolt.mana_cost

    def test_no_eligible_cards_no_crash(self) -> None:
        """If no instant/sorcery in graveyard, nothing happens."""
        game = create_game()
        p1 = game.players[0]
        card = SphinxOfForgottenLore(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        c = Creature(name='Dead', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(c)
        card.register_triggers(game)
        self._fire_and_resolve(game, EventType.ATTACKS, {'attacker': card, 'creature': card})

    def test_other_creature_attacking_no_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SphinxOfForgottenLore(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        other = Creature(name='Other', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        bolt = Instant(name='Bolt', mana_cost=ManaCost.parse('{R}'), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(bolt)
        card.register_triggers(game)
        self._fire_and_resolve(game, EventType.ATTACKS, {'attacker': other, 'creature': other})
        assert getattr(bolt, 'has_flashback', False) is False

    def test_sorcery_can_gain_flashback(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SphinxOfForgottenLore(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        sorc = Sorcery(name='Divination', mana_cost=ManaCost.parse('{2}{U}'), owner=p1)
        p1.zones[Zone.GRAVEYARD].add(sorc)
        p1._script.append(sorc)
        card.register_triggers(game)
        self._fire_and_resolve(game, EventType.ATTACKS, {'attacker': card, 'creature': card})
        assert getattr(sorc, 'has_flashback', False) is True
