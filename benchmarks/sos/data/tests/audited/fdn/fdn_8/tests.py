"""Audited tests for FDN 8 — Dauntless Veteran."""
from __future__ import annotations
from card_impl import DauntlessVeteran
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import Layer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent

class TestDauntlessVeteranBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = DauntlessVeteran(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = DauntlessVeteran(owner=None)
        assert card.name == 'Dauntless Veteran'

    def test_mana_cost(self) -> None:
        card = DauntlessVeteran(owner=None)
        assert card.mana_cost == ManaCost.parse('{1}{W}{W}')

    def test_power_toughness(self) -> None:
        card = DauntlessVeteran(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = DauntlessVeteran(owner=None)
        assert 'Human' in card.subtypes
        assert 'Soldier' in card.subtypes

class TestDauntlessVeteranAttackTrigger:
    """Attack trigger grants all creatures +1/+1 until EOT."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup_attack(self):
        game = create_game()
        p1 = game.players[0]
        vet = DauntlessVeteran(owner=p1, controller=p1)
        ally = Creature(name='Ally', base_power=2, base_toughness=2, owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(vet)
        bf.add(ally)
        vet.register_triggers(game)
        return (game, vet, ally, p1)

    def test_attack_grants_buff(self) -> None:
        game, vet, ally, p1 = self._setup_attack()
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=vet))
        self._resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ally.modified_power == 3
        assert ally.modified_toughness == 3

    def test_attack_buffs_self_too(self) -> None:
        game, vet, ally, p1 = self._setup_attack()
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=vet))
        self._resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert vet.modified_power == 3
        assert vet.modified_toughness == 3

    def test_no_buff_when_other_creature_attacks(self) -> None:
        game, vet, ally, p1 = self._setup_attack()
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=ally))
        self._resolve_stack(game)
        game.effect_manager.apply_all(game)
        assert ally.base_power == 2
        assert ally.base_toughness == 2

    def test_buff_adds_continuous_effect(self) -> None:
        game, vet, ally, p1 = self._setup_attack()
        game.trigger_manager.fire_event(game, AttacksTriggeredEvent(creature=vet))
        self._resolve_stack(game)
        effects = game.effect_manager.get_effects_by_source(vet)
        pt_effects = [e for e in effects if e.layer == Layer.POWER_TOUGHNESS]
        assert len(pt_effects) >= 1
