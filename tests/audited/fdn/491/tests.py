"""Audited tests for Bishop's Soldier (FDN collector number 491) — lifelink."""

from __future__ import annotations

import pytest

from card_impl import BishopsSoldier

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestBishopsSoldierProperties:
    def test_is_creature(self) -> None:
        card = BishopsSoldier(name="Bishop's Soldier", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = BishopsSoldier(name="Bishop's Soldier", owner=None)
        assert card.power == 2

    def test_toughness(self) -> None:
        card = BishopsSoldier(name="Bishop's Soldier", owner=None)
        assert card.toughness == 2

    def test_has_vampire_subtype(self) -> None:
        card = BishopsSoldier(name="Bishop's Soldier", owner=None)
        assert "Vampire" in card.subtypes

    def test_has_soldier_subtype(self) -> None:
        card = BishopsSoldier(name="Bishop's Soldier", owner=None)
        assert "Soldier" in card.subtypes


@pytest.mark.ability
class TestBishopsSoldierKeywords:
    def test_has_lifelink(self) -> None:
        card = BishopsSoldier(name="Bishop's Soldier", owner=None)
        assert Keyword.LIFELINK in card.keywords

    def test_only_lifelink(self) -> None:
        card = BishopsSoldier(name="Bishop's Soldier", owner=None)
        assert card.keywords == Keyword.LIFELINK


@pytest.mark.behavior
class TestBishopsSoldierBehavior:
    """Lifelink behavior: controller gains life equal to combat damage dealt."""

    def test_lifelink_gains_life_on_combat_damage(self) -> None:
        """When Bishop's Soldier deals combat damage, controller gains that much life."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = BishopsSoldier(name="Bishop's Soldier", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        initial_life = game.players[0].life
        declare_attackers(game, ["Bishop's Soldier"])
        combat_damage_step(game)
        # Controller gains 2 life (power = 2)
        assert game.players[0].life == initial_life + 2
        # Opponent loses 2 life
        assert game.players[1].life == 20 - 2
