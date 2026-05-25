"""Audited tests for FDN 217 — Dwynen, Gilt-Leaf Daen."""
from __future__ import annotations
from card_impl import DwynenGiltLeafDaen
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype
from test_utils import create_game
from engine.events import AttacksTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestDwynenBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = DwynenGiltLeafDaen(owner=None)
        assert card.name == 'Dwynen, Gilt-Leaf Daen'

    def test_mana_cost(self) -> None:
        card = DwynenGiltLeafDaen(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{G}{G}')

    def test_power_toughness(self) -> None:
        card = DwynenGiltLeafDaen(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_has_reach(self) -> None:
        card = DwynenGiltLeafDaen(owner=None)
        assert Keyword.REACH & card.keywords

    def test_is_legendary(self) -> None:
        card = DwynenGiltLeafDaen(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = DwynenGiltLeafDaen(owner=None)
        assert 'Elf' in card.subtypes
        assert 'Warrior' in card.subtypes

class TestDwynenLordEffect:
    """Other Elf creatures you control get +1/+1."""

    def test_buffs_other_elf(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dwynen = DwynenGiltLeafDaen(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dwynen)
        elf = Creature(name='Elf', base_power=1, base_toughness=1, subtypes={'Elf'}, owner=p1, controller=p1)
        game.get_battlefield(p1).add(elf)
        dwynen.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert elf.modified_power == 2
        assert elf.modified_toughness == 2

    def test_does_not_buff_self(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dwynen = DwynenGiltLeafDaen(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dwynen)
        dwynen.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert dwynen.base_power == 3
        assert dwynen.base_toughness == 4

    def test_does_not_buff_non_elf(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dwynen = DwynenGiltLeafDaen(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dwynen)
        bear = Creature(name='Bear', base_power=2, base_toughness=2, subtypes={'Bear'}, owner=p1, controller=p1)
        game.get_battlefield(p1).add(bear)
        dwynen.register_triggers(game)
        game.effect_manager.apply_all(game)
        assert bear.base_power == 2
        assert bear.base_toughness == 2

class TestDwynenAttackTrigger:
    """Whenever Dwynen attacks, gain 1 life per attacking Elf."""

    def test_gains_life_for_attacking_elves(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dwynen = DwynenGiltLeafDaen(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dwynen)
        dwynen.is_attacking = True
        elf = Creature(name='Elf', base_power=1, base_toughness=1, subtypes={'Elf'}, owner=p1, controller=p1)
        elf.is_attacking = True
        game.get_battlefield(p1).add(elf)
        dwynen.register_triggers(game)
        starting_life = p1.life
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=dwynen))
        _resolve_stack(game)
        assert p1.life == starting_life + 2
