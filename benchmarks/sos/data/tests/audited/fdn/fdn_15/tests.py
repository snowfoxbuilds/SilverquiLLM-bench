"""Audited tests for FDN 15 — Hare Apparent."""

from __future__ import annotations

from card_impl import HareApparent
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from test_utils import create_game


class TestHareApparentBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = HareApparent(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = HareApparent(owner=None)
        assert card.name == "Hare Apparent"

    def test_mana_cost(self) -> None:
        card = HareApparent(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}")

    def test_power_toughness(self) -> None:
        card = HareApparent(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = HareApparent(owner=None)
        assert "Rabbit" in card.subtypes
        assert "Noble" in card.subtypes


class TestHareApparentETB:
    """ETB creates Rabbit tokens equal to other Hare Apparents you control."""

    def test_no_other_hares_creates_no_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hare = HareApparent(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hare)
        hare.on_resolve(game)
        tokens = [
            c for c in bf.get_all()
            if getattr(c, "is_token", False) and getattr(c, "name", "") == "Rabbit"
        ]
        assert len(tokens) == 0

    def test_one_other_hare_creates_one_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hare1 = HareApparent(owner=p1, controller=p1)
        hare2 = HareApparent(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hare1)
        bf.add(hare2)
        hare2.on_resolve(game)
        tokens = [
            c for c in bf.get_all()
            if getattr(c, "is_token", False) and getattr(c, "name", "") == "Rabbit"
        ]
        assert len(tokens) == 1

    def test_two_other_hares_creates_two_tokens(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hare1 = HareApparent(owner=p1, controller=p1)
        hare2 = HareApparent(owner=p1, controller=p1)
        hare3 = HareApparent(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hare1)
        bf.add(hare2)
        bf.add(hare3)
        hare3.on_resolve(game)
        tokens = [
            c for c in bf.get_all()
            if getattr(c, "is_token", False) and getattr(c, "name", "") == "Rabbit"
        ]
        assert len(tokens) == 2

    def test_tokens_are_1_1_rabbits(self) -> None:
        game = create_game()
        p1 = game.players[0]
        hare1 = HareApparent(owner=p1, controller=p1)
        hare2 = HareApparent(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(hare1)
        bf.add(hare2)
        hare2.on_resolve(game)
        tokens = [
            c for c in bf.get_all()
            if getattr(c, "is_token", False) and getattr(c, "name", "") == "Rabbit"
        ]
        assert len(tokens) == 1
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1
        assert "Rabbit" in tokens[0].subtypes
