"""Audited tests for FDN 104 — Elvish Regrower."""

from __future__ import annotations

from card_impl import ElvishRegrower
from engine.card import Creature
from engine.triggers import EventType
from engine.types import ManaCost, Zone
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestElvishRegrowerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = ElvishRegrower(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ElvishRegrower(owner=None)
        assert card.name == "Elvish Regrower"

    def test_mana_cost(self) -> None:
        card = ElvishRegrower(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}{G}")

    def test_power_toughness(self) -> None:
        card = ElvishRegrower(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = ElvishRegrower(owner=None)
        assert "Elf" in card.subtypes
        assert "Druid" in card.subtypes


class TestElvishRegrowerETB:
    """ETB: return target permanent card from your graveyard to your hand."""

    def test_returns_card_from_graveyard_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        regrower = ElvishRegrower(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        game.get_battlefield(p1).add(regrower)
        regrower.chosen_targets = [target]
        regrower.register_triggers(game)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": regrower}
        )
        _resolve_stack(game)
        assert not p1.zones[Zone.GRAVEYARD].contains(target)
        assert p1.zones[Zone.HAND].contains(target)

    def test_no_target_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        regrower = ElvishRegrower(owner=p1, controller=p1)
        game.get_battlefield(p1).add(regrower)
        regrower.chosen_targets = [None]
        regrower.register_triggers(game)
        # Should not crash
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": regrower}
        )
        _resolve_stack(game)

    def test_only_triggers_for_self(self) -> None:
        game = create_game()
        p1 = game.players[0]
        regrower = ElvishRegrower(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(target)
        game.get_battlefield(p1).add(regrower)
        regrower.chosen_targets = [target]
        regrower.register_triggers(game)
        other = Creature(name="Other", base_power=1, base_toughness=1, owner=p1)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": other}
        )
        _resolve_stack(game)
        assert p1.zones[Zone.GRAVEYARD].contains(target)

    def test_target_not_in_graveyard_does_nothing(self) -> None:
        """If target was removed from graveyard before trigger resolves."""
        game = create_game()
        p1 = game.players[0]
        regrower = ElvishRegrower(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1)
        # target is NOT in graveyard
        game.get_battlefield(p1).add(regrower)
        regrower.chosen_targets = [target]
        regrower.register_triggers(game)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": regrower}
        )
        _resolve_stack(game)
        # Should not crash, target should not appear in hand
        assert not p1.zones[Zone.HAND].contains(target)
