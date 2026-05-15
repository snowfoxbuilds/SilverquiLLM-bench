"""Audited tests for FDN 89 — Gorehorn Raider."""

from __future__ import annotations

from card_impl import GorehornRaider
from engine.card import Creature
from engine.types import ManaCost, Zone
from tests.test_utils import create_game


class TestGorehornRaiderBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = GorehornRaider(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = GorehornRaider(owner=None)
        assert card.name == "Gorehorn Raider"

    def test_mana_cost(self) -> None:
        card = GorehornRaider(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{R}")

    def test_power_toughness(self) -> None:
        card = GorehornRaider(owner=None)
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = GorehornRaider(owner=None)
        assert "Minotaur" in card.subtypes
        assert "Pirate" in card.subtypes


class TestGorehornRaiderRaid:
    """Raid — ETB deals 2 damage to any target if attacked this turn."""

    def test_deals_2_damage_when_attacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GorehornRaider(owner=p1, controller=p1)
        game.attacked_this_turn = True
        p1._script.appendleft(p2)
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 2

    def test_no_damage_when_not_attacked(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GorehornRaider(owner=p1, controller=p1)
        game.attacked_this_turn = False
        p1.attacked_this_turn = False
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before

    def test_can_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GorehornRaider(owner=p1, controller=p1)
        game.attacked_this_turn = True
        target = Creature(name="Enemy", base_power=3, base_toughness=3, owner=p2, controller=p2)
        game.get_battlefield(p2).add(target)
        p1._script.appendleft(target)
        card.on_resolve(game)
        assert getattr(target, "damage_marked", 0) == 2

    def test_checks_controller_attacked_fallback(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = GorehornRaider(owner=p1, controller=p1)
        game.attacked_this_turn = False
        p1.attacked_this_turn = True
        p1._script.appendleft(p2)
        life_before = p2.life
        card.on_resolve(game)
        assert p2.life == life_before - 2
