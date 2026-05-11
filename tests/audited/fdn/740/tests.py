"""Audited tests for Serra Angel (FDN collector number 740) — flying + vigilance."""

from __future__ import annotations

import pytest

from card_impl import SerraAngel

from engine.card import Creature
from engine.types import Keyword


@pytest.mark.basic
class TestSerraAngelProperties:
    def test_is_creature(self) -> None:
        card = SerraAngel(name="Serra Angel", owner=None)
        assert isinstance(card, Creature)

    def test_power(self) -> None:
        card = SerraAngel(name="Serra Angel", owner=None)
        assert card.power == 4

    def test_toughness(self) -> None:
        card = SerraAngel(name="Serra Angel", owner=None)
        assert card.toughness == 4

    def test_has_angel_subtype(self) -> None:
        card = SerraAngel(name="Serra Angel", owner=None)
        assert "Angel" in card.subtypes


@pytest.mark.ability
class TestSerraAngelKeywords:
    def test_has_flying(self) -> None:
        card = SerraAngel(name="Serra Angel", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SerraAngel(name="Serra Angel", owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_exact_keywords(self) -> None:
        card = SerraAngel(name="Serra Angel", owner=None)
        expected = Keyword.FLYING | Keyword.VIGILANCE
        assert card.keywords == expected


@pytest.mark.behavior
class TestSerraAngelBehavior:
    """Flying + vigilance behavior tests."""

    def test_flying_cannot_be_blocked_by_ground(self) -> None:
        """Ground creature cannot block Serra Angel."""
        from engine.combat import _can_block
        from engine.card import Creature

        angel = SerraAngel(name="Serra Angel", owner=None)
        ground = Creature(name="Ground", owner=None)
        assert not _can_block(ground, angel)

    def test_vigilance_does_not_tap_on_attack(self) -> None:
        """Serra Angel does not tap when declared as an attacker."""
        from tests.test_utils import create_game, set_board_state, declare_attackers

        game = create_game()
        card = SerraAngel(name="Serra Angel", owner=game.players[0])
        card.summoning_sick = False
        set_board_state(game, 0, battlefield=[card])
        game.active_player_index = 0
        declare_attackers(game, ["Serra Angel"])
        assert not card.is_tapped
