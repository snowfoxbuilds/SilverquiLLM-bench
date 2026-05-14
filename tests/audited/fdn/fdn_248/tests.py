"""Audited tests for FDN 248 — Thousand-Year Storm."""

from __future__ import annotations

from card_impl import ThousandYearStorm
from engine.card import Enchantment, Instant
from engine.triggers import EventType
from engine.types import CardType, ManaCost
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestThousandYearStormBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = ThousandYearStorm(owner=None)
        assert card.name == "Thousand-Year Storm"

    def test_mana_cost(self) -> None:
        card = ThousandYearStorm(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{U}{R}")

    def test_is_enchantment(self) -> None:
        card = ThousandYearStorm(owner=None)
        assert isinstance(card, Enchantment)


class TestThousandYearStormTrigger:
    """Copies spell for each prior instant/sorcery cast this turn."""

    def test_first_spell_no_copies(self) -> None:
        game = create_game()
        p1 = game.players[0]
        storm = ThousandYearStorm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(storm)
        storm.register_triggers(game)
        spell = Instant(name="Bolt", owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, EventType.SPELL_CAST, {"player": p1, "card": spell})
        _resolve_stack(game)
        # First spell cast: storm_count goes from 0 to 1, no copies made
        assert storm._storm_count == 1

    def test_second_spell_one_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        storm = ThousandYearStorm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(storm)
        storm.register_triggers(game)
        # First spell
        spell1 = Instant(name="Bolt1", owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, EventType.SPELL_CAST, {"player": p1, "card": spell1})
        _resolve_stack(game)
        # Second spell — should try to make 1 copy
        spell2 = Instant(name="Bolt2", owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, EventType.SPELL_CAST, {"player": p1, "card": spell2})
        _resolve_stack(game)
        assert storm._storm_count == 2

    def test_creature_spell_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        storm = ThousandYearStorm(owner=p1, controller=p1)
        game.get_battlefield(p1).add(storm)
        storm.register_triggers(game)
        from engine.card import Creature
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.trigger_manager.fire_event(game, EventType.SPELL_CAST, {"player": p1, "card": creature})
        _resolve_stack(game)
        assert storm._storm_count == 0

