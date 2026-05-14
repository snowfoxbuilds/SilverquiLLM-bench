"""Audited tests for FDN 35 — Drake Hatcher."""

from __future__ import annotations

from card_impl import DrakeHatcher
from engine.card import Creature
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game


class TestDrakeHatcherBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = DrakeHatcher(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = DrakeHatcher(owner=None)
        assert card.name == "Drake Hatcher"

    def test_mana_cost(self) -> None:
        card = DrakeHatcher(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{U}")

    def test_power_toughness(self) -> None:
        card = DrakeHatcher(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_has_vigilance(self) -> None:
        card = DrakeHatcher(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_has_prowess(self) -> None:
        card = DrakeHatcher(owner=None)
        assert Keyword.PROWESS in card.keywords

    def test_subtypes(self) -> None:
        card = DrakeHatcher(owner=None)
        assert "Human" in card.subtypes
        assert "Wizard" in card.subtypes


class TestDrakeHatcherCombatDamageTrigger:
    """Whenever this deals combat damage to a player, add incubation counters."""

    @staticmethod
    def _resolve_stack(game):
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        hatcher = DrakeHatcher(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hatcher)
        hatcher.register_triggers(game)
        return game, hatcher, p1, p2

    def test_gains_incubation_counters_on_combat_damage(self) -> None:
        from engine.triggers import EventType
        game, hatcher, p1, p2 = self._setup()
        game.trigger_manager.fire_event(
            game, EventType.DEALS_DAMAGE,
            {"source": hatcher, "target": p2, "is_combat": True, "amount": 1},
        )
        self._resolve_stack(game)
        assert hatcher.incubation_counters >= 1

    def test_no_counters_on_non_combat_damage(self) -> None:
        from engine.triggers import EventType
        game, hatcher, p1, p2 = self._setup()
        game.trigger_manager.fire_event(
            game, EventType.DEALS_DAMAGE,
            {"source": hatcher, "target": p2, "is_combat": False, "amount": 1},
        )
        self._resolve_stack(game)
        assert hatcher.incubation_counters == 0


class TestDrakeHatcherActivatedAbility:
    """Remove three incubation counters: Create 2/2 Drake token with flying."""

    def test_has_activated_ability(self) -> None:
        card = DrakeHatcher(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_ability_requires_three_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hatcher = DrakeHatcher(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hatcher)
        hatcher.incubation_counters = 2
        ability = hatcher.get_activated_abilities()[0]
        # Cost should fail with only 2 counters
        result = ability.cost(game, hatcher)
        assert result is False
        assert hatcher.incubation_counters == 2

    def test_ability_creates_drake_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hatcher = DrakeHatcher(owner=p1, controller=p1)
        game.get_battlefield(p1).add(hatcher)
        hatcher.incubation_counters = 3
        ability = hatcher.get_activated_abilities()[0]
        paid = ability.cost(game, hatcher)
        assert paid is True
        assert hatcher.incubation_counters == 0
        ability.effect(game)
        bf = game.get_battlefield(p1)
        tokens = [c for c in bf.get_all() if getattr(c, "name", "") == "Drake"]
        assert len(tokens) == 1
        assert tokens[0].base_power == 2
        assert tokens[0].base_toughness == 2
        assert Keyword.FLYING in tokens[0].keywords
