"""Audited tests for FDN 67 — Revenge of the Rats."""

from __future__ import annotations

from card_impl import RevengeOfTheRats
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Zone
from tests.test_utils import create_game


class TestRevengeOfTheRatsBasics:
    """Basic card properties."""

    def test_is_sorcery(self) -> None:
        card = RevengeOfTheRats(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        card = RevengeOfTheRats(owner=None)
        assert card.name == "Revenge of the Rats"

    def test_mana_cost(self) -> None:
        card = RevengeOfTheRats(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{B}{B}")


class TestRevengeOfTheRatsResolve:
    """Create tapped 1/1 Rat tokens for each creature card in graveyard."""

    def test_creates_tokens_equal_to_graveyard_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RevengeOfTheRats(owner=p1, controller=p1)
        for i in range(3):
            c = Creature(name=f"Dead{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        rats = [c for c in bf.get_all() if getattr(c, "name", "") == "Rat"]
        assert len(rats) == 3

    def test_tokens_are_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RevengeOfTheRats(owner=p1, controller=p1)
        c = Creature(name="Dead", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(c)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        rats = [c for c in bf.get_all() if getattr(c, "name", "") == "Rat"]
        assert len(rats) == 1
        assert getattr(rats[0], "tapped", False) or getattr(rats[0], "is_tapped", False)

    def test_tokens_are_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RevengeOfTheRats(owner=p1, controller=p1)
        c = Creature(name="Dead", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(c)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        rats = [c for c in bf.get_all() if getattr(c, "name", "") == "Rat"]
        assert rats[0].base_power == 1
        assert rats[0].base_toughness == 1

    def test_no_tokens_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = RevengeOfTheRats(owner=p1, controller=p1)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        assert len(bf.get_all()) == 0

    def test_only_counts_creature_cards(self) -> None:
        """Non-creature cards in graveyard should not count."""
        game = create_game()
        p1 = game.players[0]
        card = RevengeOfTheRats(owner=p1, controller=p1)
        # Add a creature
        c = Creature(name="Dead", base_power=1, base_toughness=1, owner=p1)
        p1.zones[Zone.GRAVEYARD].add(c)
        # Add a non-creature (instant)
        from engine.card import Instant
        inst = Instant(name="Spell", owner=p1)
        p1.zones[Zone.GRAVEYARD].add(inst)
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        rats = [c for c in bf.get_all() if getattr(c, "name", "") == "Rat"]
        assert len(rats) == 1
