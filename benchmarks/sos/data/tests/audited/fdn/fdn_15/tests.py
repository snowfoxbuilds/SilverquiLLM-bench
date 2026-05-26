"""Audited tests for FDN 15 — Bigfin Bouncer (Merfolk Rogue ETB-bounce slot)."""

from __future__ import annotations

from card_impl import BigfinBouncer
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestBigfinBouncerBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = BigfinBouncer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = BigfinBouncer(owner=None)
        assert card.name == "Bigfin Bouncer"

    def test_mana_cost(self) -> None:
        card = BigfinBouncer(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{U}")

    def test_power_toughness(self) -> None:
        card = BigfinBouncer(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = BigfinBouncer(owner=None)
        assert "Merfolk" in card.subtypes
        assert "Rogue" in card.subtypes


class TestBigfinBouncerETB:
    """When this creature enters, return target opponent's creature to hand."""

    def test_bounces_opponent_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(
            name="Enemy Bear", base_power=2, base_toughness=2,
            owner=p2, controller=p2,
        )
        game.get_battlefield(p2).add(target)
        bouncer = BigfinBouncer(owner=p1, controller=p1)
        bouncer.chosen_targets = [target]
        bouncer.on_resolve(game)
        bf_names = [getattr(c, "name", "") for c in game.get_battlefield(p2).get_all()]
        assert "Enemy Bear" not in bf_names
        hand_names = [getattr(c, "name", "") for c in p2.zones[Zone.HAND].get_all()]
        assert "Enemy Bear" in hand_names

    def test_no_crash_without_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bouncer = BigfinBouncer(owner=p1, controller=p1)
        bouncer.chosen_targets = []
        bouncer.on_resolve(game)  # Should not raise

    def test_does_not_bounce_own_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        own_creature = Creature(
            name="Own Bear", base_power=2, base_toughness=2,
            owner=p1, controller=p1,
        )
        game.get_battlefield(p1).add(own_creature)
        bouncer = BigfinBouncer(owner=p1, controller=p1)
        bouncer.chosen_targets = [own_creature]
        bouncer.on_resolve(game)
        bf_names = [getattr(c, "name", "") for c in game.get_battlefield(p1).get_all()]
        assert "Own Bear" in bf_names
