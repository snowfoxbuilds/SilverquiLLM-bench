"""Audited tests for Healer's Hawk (FDN collector number 734) — flying + lifelink."""

from __future__ import annotations

import pytest

from card_impl import HealersHawk

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestHealersHawkProperties:
    def test_is_creature(self) -> None:
        card = HealersHawk(name="Healer's Hawk", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = HealersHawk(name="Healer's Hawk", owner=None)
        assert card.power == 1

    def test_toughness(self) -> None:
        card = HealersHawk(name="Healer's Hawk", owner=None)
        assert card.toughness == 1

    def test_has_bird_subtype(self) -> None:
        card = HealersHawk(name="Healer's Hawk", owner=None)
        assert "Bird" in card.subtypes


@pytest.mark.ability
class TestHealersHawkKeywords:
    def test_has_flying(self) -> None:
        card = HealersHawk(name="Healer's Hawk", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_lifelink(self) -> None:
        card = HealersHawk(name="Healer's Hawk", owner=None)
        assert Keyword.LIFELINK in card.keywords

    def test_no_other_keywords(self) -> None:
        card = HealersHawk(name="Healer's Hawk", owner=None)
        expected = Keyword.FLYING | Keyword.LIFELINK
        assert card.keywords == expected


@pytest.mark.behavior
class TestHealersHawkBehavior:
    """Flying + lifelink behavior tests."""

    def test_flying_cannot_be_blocked_by_ground(self) -> None:
        """Ground creature cannot block Healer's Hawk."""
        from engine.combat import _can_block
        from engine.card import Creature

        hawk = HealersHawk(name="Healer's Hawk", owner=None)
        ground = Creature(name="Ground", owner=None)
        assert not _can_block(ground, hawk)

    def test_lifelink_gains_life_on_combat_damage(self) -> None:
        """Controller gains life equal to combat damage dealt by lifelink creature."""
        from tests.test_utils import create_game, set_board_state, declare_attackers
        from engine.combat import combat_damage_step

        game = create_game()
        card = HealersHawk(name="Healer's Hawk", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        initial_life = game.players[0].life
        declare_attackers(game, ["Healer's Hawk"])
        combat_damage_step(game)
        assert game.players[0].life == initial_life + 1
