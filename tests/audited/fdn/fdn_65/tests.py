"""Audited tests for FDN 65 — Midnight Snack."""

from __future__ import annotations

from card_impl import MidnightSnack
from engine.card import Enchantment
from engine.types import ManaCost, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestMidnightSnackBasics:
    """Basic card properties."""

    def test_is_enchantment(self) -> None:
        card = MidnightSnack(owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        card = MidnightSnack(owner=None)
        assert card.name == "Midnight Snack"

    def test_mana_cost(self) -> None:
        card = MidnightSnack(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{B}")


class TestMidnightSnackActivatedAbility:
    """Sacrifice ability: target opponent loses X life (life gained this turn)."""

    def test_has_activated_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MidnightSnack(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        assert len(abilities) >= 1

    def test_sac_ability_drains_opponent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MidnightSnack(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        p1.life_gained_this_turn = 5
        p2_life_before = p2.life
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        assert p2.life == p2_life_before - 5

    def test_sac_ability_no_drain_if_no_life_gained(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = MidnightSnack(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        p1.life_gained_this_turn = 0
        p2_life_before = p2.life
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        assert p2.life == p2_life_before

    def test_sac_ability_sacrifices_enchantment(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = MidnightSnack(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        p1.life_gained_this_turn = 0
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        assert not game.get_battlefield(p1).contains(card)
