"""Audited tests for FDN 70 — Soul-Shackled Zombie."""

from __future__ import annotations

from card_impl import SoulShackledZombie
from engine.card import Creature
from engine.types import ManaCost, Zone
from tests.test_utils import create_game


class TestSoulShackledZombieBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = SoulShackledZombie(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = SoulShackledZombie(owner=None)
        assert card.name == "Soul-Shackled Zombie"

    def test_mana_cost(self) -> None:
        card = SoulShackledZombie(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{B}")

    def test_power_toughness(self) -> None:
        card = SoulShackledZombie(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = SoulShackledZombie(owner=None)
        assert "Zombie" in card.subtypes


class TestSoulShackledZombieETB:
    """ETB: exile up to 2 cards from a graveyard; drain if creature exiled."""

    def test_exiles_creature_and_drains(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SoulShackledZombie(owner=p1, controller=p1)
        target = Creature(name="Dead", base_power=2, base_toughness=2, owner=p2)
        p2.zones[Zone.GRAVEYARD].add(target)
        p2_life_before = p2.life
        p1_life_before = p1.life
        card.on_resolve(game)
        assert not p2.zones[Zone.GRAVEYARD].contains(target)
        assert p2.life == p2_life_before - 2
        assert p1.life == p1_life_before + 2

    def test_no_drain_with_empty_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SoulShackledZombie(owner=p1, controller=p1)
        p2_life_before = p2.life
        p1_life_before = p1.life
        card.on_resolve(game)
        assert p2.life == p2_life_before
        assert p1.life == p1_life_before

    def test_exiles_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = SoulShackledZombie(owner=p1, controller=p1)
        target = Creature(name="Dead", base_power=2, base_toughness=2, owner=p2)
        p2.zones[Zone.GRAVEYARD].add(target)
        card.on_resolve(game)
        assert not p2.zones[Zone.GRAVEYARD].contains(target)
