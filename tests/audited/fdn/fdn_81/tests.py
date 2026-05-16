"""Audited tests for FDN 81 — Chandra, Flameshaper."""
from __future__ import annotations
import pytest
from card_impl import ChandraFlameshaper
from engine.card import Creature, Planeswalker
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from tests.test_utils import create_game, set_board_state
from engine.events import EndStepTriggeredEvent

class TestChandraBasics:
    """Basic card properties."""

    def test_is_planeswalker(self) -> None:
        card = ChandraFlameshaper(owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types

    def test_mana_cost(self) -> None:
        card = ChandraFlameshaper(owner=None)
        assert card.mana_cost == ManaCost.parse('{5}{R}{R}')

    def test_starting_loyalty_is_6(self) -> None:
        card = ChandraFlameshaper(owner=None)
        assert card.starting_loyalty == 6
        assert card.loyalty == 6

    def test_is_legendary(self) -> None:
        card = ChandraFlameshaper(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_chandra_subtype(self) -> None:
        card = ChandraFlameshaper(owner=None)
        assert 'Chandra' in card.subtypes

    def test_has_three_loyalty_abilities(self) -> None:
        card = ChandraFlameshaper(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 3

    def test_loyalty_costs_are_plus2_plus1_minus4(self) -> None:
        card = ChandraFlameshaper(owner=None)
        abilities = card.get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +2
        assert abilities[1].loyalty_cost == +1
        assert abilities[2].loyalty_cost == -4

class TestChandraPlus2:
    """+2: Add {R}{R}{R}. Exile top 3, may play one this turn."""

    def test_plus2_adds_three_red_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        for i in range(5):
            card = Creature(name=f'Card{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(card)
        initial_red = p1.mana_pool.get(ManaType.RED)
        abilities = chandra.get_loyalty_abilities()
        abilities[0].effect(game)
        assert p1.mana_pool.get(ManaType.RED) == initial_red + 3

    def test_plus2_exiles_three_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        for i in range(5):
            card = Creature(name=f'Card{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(card)
        abilities = chandra.get_loyalty_abilities()
        abilities[0].effect(game)
        exile = p1.zones[Zone.EXILE]
        assert len(exile) == 3
        assert len(p1.zones[Zone.LIBRARY]) == 2

    def test_plus2_marks_exiled_cards_as_playable(self) -> None:
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        for i in range(3):
            card = Creature(name=f'Card{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(card)
        abilities = chandra.get_loyalty_abilities()
        abilities[0].effect(game)
        exile = p1.zones[Zone.EXILE]
        exiled = exile.get_all()
        playable = [c for c in exiled if getattr(c, '_playable_this_turn', False)]
        assert len(playable) > 0

    def test_plus2_only_chosen_card_is_playable(self) -> None:
        """Oracle says 'Choose one. You may play that card this turn.' — only one card is playable."""
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        for i in range(3):
            card = Creature(name=f'Card{i}', base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(card)
        abilities = chandra.get_loyalty_abilities()
        abilities[0].effect(game)
        exile = p1.zones[Zone.EXILE]
        exiled = exile.get_all()
        playable = [c for c in exiled if getattr(c, '_playable_this_turn', False)]
        assert len(playable) == 1

    def test_plus2_with_fewer_than_3_cards_exiles_what_is_available(self) -> None:
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        card = Creature(name='Lonely', base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.LIBRARY].add(card)
        abilities = chandra.get_loyalty_abilities()
        abilities[0].effect(game)
        exile = p1.zones[Zone.EXILE]
        assert len(exile) == 1

class TestChandraPlus1:
    """+1: Create token copy of target creature (haste, sacrifice at end step)."""

    def test_plus1_creates_token_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        target = Creature(name='Dragon', base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        game.get_battlefield(p1).add(target)
        chandra._resolve_target = target
        abilities = chandra.get_loyalty_abilities()
        abilities[1].effect(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.name == 'Dragon'
        assert token.base_power == 5
        assert token.base_toughness == 5

    def test_plus1_token_has_haste(self) -> None:
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        target = Creature(name='Dragon', base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        game.get_battlefield(p1).add(target)
        chandra._resolve_target = target
        abilities = chandra.get_loyalty_abilities()
        abilities[1].effect(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        token = tokens[0]
        assert Keyword.HASTE in token.keywords

    def test_plus1_token_sacrificed_at_end_step(self) -> None:
        """The copied token has 'At the beginning of the end step, sacrifice this token.'"""
        game = create_game()
        p1 = game.players[0]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        target = Creature(name='Dragon', base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(chandra)
        game.get_battlefield(p1).add(target)
        chandra._resolve_target = target
        abilities = chandra.get_loyalty_abilities()
        abilities[1].effect(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        assert len(tokens) == 1
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens_after = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        assert len(tokens_after) == 0

class TestChandraMinus4:
    """−4: Deal 8 damage divided among targets."""

    def test_minus4_deals_8_damage_to_single_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        target = Creature(name='Giant', base_power=4, base_toughness=10, owner=p2, controller=p2)
        target.damage_marked = 0
        game.get_battlefield(p1).add(chandra)
        game.get_battlefield(p2).add(target)
        chandra._resolve_target = target
        abilities = chandra.get_loyalty_abilities()
        abilities[2].effect(game)
        assert target.damage_marked == 8

    def test_minus4_divides_damage_among_multiple_targets(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        t1 = Creature(name='Goblin', base_power=1, base_toughness=1, owner=p2, controller=p2)
        t2 = Creature(name='Elf', base_power=1, base_toughness=1, owner=p2, controller=p2)
        t1.damage_marked = 0
        t2.damage_marked = 0
        game.get_battlefield(p1).add(chandra)
        game.get_battlefield(p2).add(t1)
        game.get_battlefield(p2).add(t2)
        chandra._damage_assignments = [(t1, 5), (t2, 3)]
        abilities = chandra.get_loyalty_abilities()
        abilities[2].effect(game)
        assert t1.damage_marked == 5
        assert t2.damage_marked == 3

    def test_minus4_total_damage_is_8_with_assignments(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        chandra = ChandraFlameshaper(owner=p1, controller=p1)
        t1 = Creature(name='A', base_power=1, base_toughness=10, owner=p2, controller=p2)
        t2 = Creature(name='B', base_power=1, base_toughness=10, owner=p2, controller=p2)
        t3 = Creature(name='C', base_power=1, base_toughness=10, owner=p2, controller=p2)
        t1.damage_marked = 0
        t2.damage_marked = 0
        t3.damage_marked = 0
        game.get_battlefield(p1).add(chandra)
        game.get_battlefield(p2).add(t1)
        game.get_battlefield(p2).add(t2)
        game.get_battlefield(p2).add(t3)
        chandra._damage_assignments = [(t1, 3), (t2, 3), (t3, 2)]
        abilities = chandra.get_loyalty_abilities()
        abilities[2].effect(game)
        total = t1.damage_marked + t2.damage_marked + t3.damage_marked
        assert total == 8
