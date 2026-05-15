"""Audited tests for FDN 170 — Burglar Rat."""

from __future__ import annotations

from card_impl import BurglarRat
from engine.card import CardImpl, Creature
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, Zone
from tests.test_utils import create_game


def _resolve_stack(game):
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


class TestBurglarRatBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = BurglarRat(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BurglarRat(owner=None)
        assert card.name == "Burglar Rat"

    def test_mana_cost(self) -> None:
        card = BurglarRat(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")

    def test_power_toughness(self) -> None:
        card = BurglarRat(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_subtypes(self) -> None:
        card = BurglarRat(owner=None)
        assert "Rat" in card.subtypes


class TestBurglarRatETB:
    """When this creature enters, each opponent discards a card."""

    def test_opponent_discards_on_etb(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        rat = BurglarRat(owner=p1, controller=p1)
        # Give opponent a card in hand
        dummy = CardImpl(name="Dummy", mana_cost=ManaCost(generic=0), owner=p2, controller=p2)
        game.get_hand(p2).add(dummy)
        hand_before = len(game.get_hand(p2).get_all())
        game.get_battlefield(p1).add(rat)
        rat.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": rat})
        _resolve_stack(game)
        hand_after = len(game.get_hand(p2).get_all())
        assert hand_after == hand_before - 1

    def test_controller_does_not_discard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        rat = BurglarRat(owner=p1, controller=p1)
        card_in_hand = CardImpl(name="MyCard", mana_cost=ManaCost(generic=0), owner=p1, controller=p1)
        game.get_hand(p1).add(card_in_hand)
        dummy = CardImpl(name="OppCard", mana_cost=ManaCost(generic=0), owner=p2, controller=p2)
        game.get_hand(p2).add(dummy)
        hand_before = len(game.get_hand(p1).get_all())
        game.get_battlefield(p1).add(rat)
        rat.register_triggers(game)
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD, {"permanent": rat})
        _resolve_stack(game)
        assert len(game.get_hand(p1).get_all()) == hand_before
