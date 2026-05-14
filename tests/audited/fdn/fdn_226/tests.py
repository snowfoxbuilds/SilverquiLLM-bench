"""Audited tests for FDN 226 — Inspiring Call."""

from __future__ import annotations

from card_impl import InspiringCall
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Zone
from tests.test_utils import create_game


class TestInspiringCallBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = InspiringCall(owner=None)
        assert card.name == "Inspiring Call"

    def test_mana_cost(self) -> None:
        card = InspiringCall(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}")

    def test_is_instant(self) -> None:
        card = InspiringCall(owner=None)
        assert isinstance(card, Instant)


class TestInspiringCallResolve:
    """Draw cards and grant indestructible to creatures with +1/+1 counters."""

    def test_draws_for_creatures_with_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c1.plus_one_counters = 1
        c2 = Creature(name="Elk", base_power=3, base_toughness=3, owner=p1, controller=p1)
        c2.plus_one_counters = 2
        c3 = Creature(name="Fox", base_power=1, base_toughness=1, owner=p1, controller=p1)
        # c3 has no counters
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p1).add(c2)
        game.get_battlefield(p1).add(c3)
        # Put cards in library to draw
        from engine.card import CardImpl
        for i in range(5):
            p1.zones[Zone.LIBRARY].add(CardImpl(name=f"Card{i}", owner=p1))
        spell = InspiringCall(owner=p1, controller=p1)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after - hand_before == 2  # 2 creatures with counters

    def test_grants_indestructible(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        c1.plus_one_counters = 1
        game.get_battlefield(p1).add(c1)
        from engine.card import CardImpl
        p1.zones[Zone.LIBRARY].add(CardImpl(name="Card", owner=p1))
        spell = InspiringCall(owner=p1, controller=p1)
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE & c1.keywords

    def test_no_counters_no_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]
        c1 = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(c1)
        spell = InspiringCall(owner=p1, controller=p1)
        hand_before = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        hand_after = len(list(p1.zones[Zone.HAND].get_all()))
        assert hand_after == hand_before

