"""Audited tests for FDN 205 — Wardens of the Cycle (Converge reference slot)."""

from __future__ import annotations

from card_impl import WardensOfTheCycle
from engine.card import Creature
from engine.types import ManaCost
from test_utils import create_game


class TestWardensOfTheCycleBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.name == "Wardens of the Cycle"

    def test_mana_cost(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}{G}")

    def test_power_toughness(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = WardensOfTheCycle(owner=None)
        assert "Treefolk" in card.subtypes


class TestWardensOfTheCycleConverge:
    """ETB creates one 1/1 Saproling token per color of mana spent to cast."""

    def test_no_tokens_when_no_colors_spent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        wardens.colors_spent = 0
        bf_before = len(game.get_battlefield(p1).get_all())
        wardens.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after - bf_before == 0

    def test_creates_one_token_per_color(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        wardens.colors_spent = 2  # {B} + {G}
        bf_before = len(game.get_battlefield(p1).get_all())
        wardens.on_resolve(game)
        bf_after = len(game.get_battlefield(p1).get_all())
        assert bf_after - bf_before == 2

    def test_tokens_are_saprolings(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        wardens.colors_spent = 3
        wardens.on_resolve(game)
        saproling_count = sum(
            1 for c in game.get_battlefield(p1).get_all()
            if getattr(c, "name", "") == "Saproling"
        )
        assert saproling_count == 3

    def test_tokens_are_one_one(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wardens = WardensOfTheCycle(owner=p1, controller=p1)
        wardens.colors_spent = 1
        wardens.on_resolve(game)
        tokens = [
            c for c in game.get_battlefield(p1).get_all()
            if getattr(c, "name", "") == "Saproling"
        ]
        assert len(tokens) == 1
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1
