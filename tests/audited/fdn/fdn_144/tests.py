"""Audited tests for FDN 144 — Mischievous Pup."""

from __future__ import annotations

from card_impl import MischievousPup
from engine.card import CardImpl, Creature
from engine.triggers import EventType
from engine.types import ManaCost, Zone
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestMischievousPupBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = MischievousPup(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = MischievousPup(owner=None)
        assert card.name == "Mischievous Pup"

    def test_mana_cost(self) -> None:
        card = MischievousPup(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}")

    def test_power_toughness(self) -> None:
        card = MischievousPup(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 1

    def test_dog_subtype(self) -> None:
        card = MischievousPup(owner=None)
        assert "Dog" in card.subtypes


class TestMischievousPupETB:
    """When ETB, return up to one other target permanent you control to hand."""

    def test_bounces_target_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pup = MischievousPup(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(pup)
        game.get_battlefield(p1).add(target)
        pup.chosen_targets = [target]
        pup.register_triggers(game)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": pup}
        )
        _resolve_stack(game)
        bf_names = [getattr(c, "name", "") for c in game.get_battlefield(p1).get_all()]
        assert "Bear" not in bf_names

    def test_bounced_card_goes_to_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pup = MischievousPup(owner=p1, controller=p1)
        target = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(pup)
        game.get_battlefield(p1).add(target)
        pup.chosen_targets = [target]
        pup.register_triggers(game)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": pup}
        )
        _resolve_stack(game)
        hand_names = [getattr(c, "name", "") for c in p1.zones[Zone.HAND].get_all()]
        assert "Bear" in hand_names

    def test_no_target_does_nothing(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pup = MischievousPup(owner=p1, controller=p1)
        game.get_battlefield(p1).add(pup)
        pup.register_triggers(game)
        game.trigger_manager.fire_event(
            game, EventType.ENTERS_BATTLEFIELD, {"permanent": pup}
        )
        _resolve_stack(game)
        # Pup is still on battlefield, nothing crashed
        assert game.get_battlefield(p1).contains(pup)
