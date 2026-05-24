"""Audited tests for FDN 242 — Lathril, Blade of the Elves."""
from __future__ import annotations
from card_impl import LathrilBladeOfTheElves
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Supertype
from benchmarks.sos.workspace.tests.test_utils import create_game
from benchmarks.sos.workspace.engine.events import DealsDamageTriggeredEvent

def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)

class TestLathrilBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = LathrilBladeOfTheElves(owner=None)
        assert card.name == 'Lathril, Blade of the Elves'

    def test_mana_cost(self) -> None:
        card = LathrilBladeOfTheElves(owner=None)
        assert card.mana_cost == ManaCost.parse('{2}{B}{G}')

    def test_power_toughness(self) -> None:
        card = LathrilBladeOfTheElves(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_has_menace(self) -> None:
        card = LathrilBladeOfTheElves(owner=None)
        assert Keyword.MENACE & card.keywords

    def test_is_legendary(self) -> None:
        card = LathrilBladeOfTheElves(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes(self) -> None:
        card = LathrilBladeOfTheElves(owner=None)
        assert 'Elf' in card.subtypes
        assert 'Noble' in card.subtypes

class TestLathrilCombatDamageTrigger:
    """Creates tokens equal to combat damage dealt to player."""

    def test_creates_tokens_on_combat_damage(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        lathril = LathrilBladeOfTheElves(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lathril)
        lathril.register_triggers(game)
        game.trigger_manager.fire_event(game, DealsDamageTriggeredEvent(source=lathril, target=p2, amount=2))
        _resolve_stack(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, 'is_token', False)]
        assert len(tokens) == 2
        for t in tokens:
            assert 'Elf' in t.subtypes

class TestLathrilActivatedAbility:
    """Tap + 10 elves: opponents lose 10 life, you gain 10."""

    def test_activated_ability_exists(self) -> None:
        lathril = LathrilBladeOfTheElves(owner=None)
        abilities = lathril.get_activated_abilities()
        assert len(abilities) >= 1
