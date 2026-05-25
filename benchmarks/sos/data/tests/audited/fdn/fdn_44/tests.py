"""Audited tests for FDN 44 — Kaito, Cunning Infiltrator."""
from __future__ import annotations
import pytest
from card_impl import KaitoCunningInfiltrator
from engine.card import Creature, Planeswalker
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state
from engine.events import DealsDamageTriggeredEvent, SpellCastTriggeredEvent

class TestKaitoBasics:
    """Basic card properties."""

    def test_is_planeswalker(self) -> None:
        card = KaitoCunningInfiltrator(owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types

    def test_mana_cost(self) -> None:
        card = KaitoCunningInfiltrator(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{U}{U}')

    def test_starting_loyalty_is_3(self) -> None:
        card = KaitoCunningInfiltrator(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_is_legendary(self) -> None:
        card = KaitoCunningInfiltrator(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_kaito_subtype(self) -> None:
        card = KaitoCunningInfiltrator(owner=None)
        assert 'Kaito' in card.subtypes

    def test_has_three_loyalty_abilities(self) -> None:
        card = KaitoCunningInfiltrator(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs_are_plus1_minus2_minus9(self) -> None:
        card = KaitoCunningInfiltrator(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1
        assert abilities[1].loyalty_cost == -2
        assert abilities[2].loyalty_cost == -9

class TestKaitoPassive:
    """Passive: combat damage to a player → loyalty counter."""

    def _resolve_stack(self, game) -> None:
        """Resolve all triggers on the stack."""
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_passive_triggers_on_combat_damage_to_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        game.get_battlefield(p1).add(creature)
        kaito.register_triggers(game)
        initial_loyalty = kaito.loyalty
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=creature, target=game.players[1], amount=2, combat=True))
        self._resolve_stack(game)
        assert kaito.loyalty == initial_loyalty + 1

    def test_passive_does_not_trigger_on_damage_to_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        creature = Creature(name='Bear', base_power=2, base_toughness=2, owner=p1, controller=p1)
        target_creature = Creature(name='Wall', base_power=0, base_toughness=4, owner=p2, controller=p2)
        game.get_battlefield(p1).add(kaito)
        game.get_battlefield(p1).add(creature)
        kaito.register_triggers(game)
        initial_loyalty = kaito.loyalty
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=creature, target=target_creature, amount=2))
        self._resolve_stack(game)
        assert kaito.loyalty == initial_loyalty

    def test_passive_does_not_trigger_on_noncombat_damage_to_player(self) -> None:
        """Noncombat damage (e.g. from a spell/ability) should NOT add loyalty."""
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        creature = Creature(name='Pinger', base_power=1, base_toughness=1, owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        game.get_battlefield(p1).add(creature)
        kaito.register_triggers(game)
        initial_loyalty = kaito.loyalty
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=creature, target=game.players[1], amount=1, combat=False))
        self._resolve_stack(game)
        assert kaito.loyalty == initial_loyalty

    def test_passive_does_not_trigger_for_opponent_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        opp_creature = Creature(name='Goblin', base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p1).add(kaito)
        game.get_battlefield(p2).add(opp_creature)
        kaito.register_triggers(game)
        initial_loyalty = kaito.loyalty
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=opp_creature, target=p1, amount=1))
        self._resolve_stack(game)
        assert kaito.loyalty == initial_loyalty

class TestKaitoPlus1:
    """+1: can't be blocked + loot (draw then discard)."""

    def test_plus1_draws_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        lib_card = Creature(name='Fish', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        hand_card = Creature(name='Otter', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.HAND].add(hand_card)
        abilities = kaito.get_loyalty_abilities()
        plus1 = abilities[0]
        plus1.effect(game)
        graveyard = p1.zones[Zone.GRAVEYARD]
        assert len(graveyard) == 1

    def test_plus1_loots_discards_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        lib_card = Creature(name='Fish', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(lib_card)
        abilities = kaito.get_loyalty_abilities()
        plus1 = abilities[0]
        plus1.effect(game)
        assert len(p1.zones[Zone.GRAVEYARD]) == 1

class TestKaitoMinus2:
    """−2: Create a 2/1 blue Ninja creature token."""

    def test_minus2_creates_ninja_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        abilities = kaito.get_loyalty_abilities()
        minus2 = abilities[1]
        minus2.effect(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.name == 'Ninja'
        assert token.base_power == 2
        assert token.base_toughness == 1

    def test_minus2_token_is_creature_with_ninja_subtype(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        abilities = kaito.get_loyalty_abilities()
        abilities[1].effect(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        token = tokens[0]
        assert CardType.CREATURE in token.card_types
        assert 'Ninja' in token.subtypes

class TestKaitoMinus9:
    """−9: Emblem — whenever a player casts a spell, create 2/1 Ninja token."""

    def _resolve_stack(self, game) -> None:
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_minus9_registers_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        abilities = kaito.get_loyalty_abilities()
        minus9 = abilities[2]
        minus9.effect(game)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=game.players[1], spell=None))
        self._resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        assert len(tokens) == 1
        assert tokens[0].name == 'Ninja'
        assert tokens[0].base_power == 2
        assert tokens[0].base_toughness == 1

    def test_minus9_fires_for_any_player_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        kaito = KaitoCunningInfiltrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(kaito)
        abilities = kaito.get_loyalty_abilities()
        abilities[2].effect(game)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=p1, spell=None))
        self._resolve_stack(game)
        game.trigger_manager.fire_event(game, SpellCastTriggeredEvent(player=game.players[1], spell=None))
        self._resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        assert len(tokens) == 2
