"""Audited tests for FDN 98 — Ambush Wolf."""

from __future__ import annotations

from card_impl import AmbushWolf
from engine.card import Creature
from engine.triggers import EventType
from engine.types import Keyword, ManaCost, Zone
from tests.test_utils import create_game


def _resolve_stack(game):
    """Pop and resolve all objects on the stack."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestAmbushWolfBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = AmbushWolf(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = AmbushWolf(owner=None)
        assert card.name == "Ambush Wolf"

    def test_mana_cost(self) -> None:
        card = AmbushWolf(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}")

    def test_power_toughness(self) -> None:
        card = AmbushWolf(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 2

    def test_has_flash(self) -> None:
        card = AmbushWolf(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_subtypes(self) -> None:
        card = AmbushWolf(owner=None)
        assert "Wolf" in card.subtypes


class TestAmbushWolfETB:
    """ETB: exile up to one target card from a graveyard."""

    def test_etb_exiles_card_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wolf = AmbushWolf(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2)
        p2.zones[Zone.GRAVEYARD].add(target)
        game.get_battlefield(p1).add(wolf)
        wolf.chosen_targets = [target]
        wolf.register_triggers(game)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": wolf}
        )
        _resolve_stack(game)
        assert not p2.zones[Zone.GRAVEYARD].contains(target)
        assert p2.zones[Zone.EXILE].contains(target)

    def test_etb_no_target_does_nothing(self) -> None:
        """With no target chosen, ETB does nothing (up to one)."""
        game = create_game()
        p1 = game.players[0]
        wolf = AmbushWolf(owner=p1, controller=p1)
        game.get_battlefield(p1).add(wolf)
        wolf.chosen_targets = [None]
        wolf.register_triggers(game)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": wolf}
        )
        _resolve_stack(game)

    def test_etb_only_triggers_for_self(self) -> None:
        """ETB trigger should only fire when Ambush Wolf itself enters."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        wolf = AmbushWolf(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2)
        p2.zones[Zone.GRAVEYARD].add(target)
        game.get_battlefield(p1).add(wolf)
        wolf.chosen_targets = [target]
        wolf.register_triggers(game)
        other = Creature(name="Other", base_power=1, base_toughness=1, owner=p1)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": other}
        )
        _resolve_stack(game)
        assert p2.zones[Zone.GRAVEYARD].contains(target)
