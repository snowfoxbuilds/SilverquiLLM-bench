"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType
from test_utils import TestSetupError, cast_spell, create_game, set_board_state


def _bears(n):
    return [
        Creature(name=f"Bear {i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


class TestWitherbloomSelfAffinity:
    def test_own_cost_reduced_by_creatures_you_control(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(
            game, 0, battlefield=_bears(3), hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        # {6}{B}{G} - 3 creatures = {3}{B}{G}
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(game.players[0]).contains(wb)

    def test_no_creatures_full_price(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(
            game, 0, hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 5},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_opponent_creatures_do_not_count(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 1, battlefield=_bears(4))
        set_board_state(
            game, 0, hand=[wb],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 2},
        )
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_keywords(self):
        wb = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in wb.keywords
        assert Keyword.DEATHTOUCH in wb.keywords


class TestWitherbloomGrantsAffinity:
    def test_your_instants_cost_less_per_creature(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        spell = Instant(name="Big Trick", mana_cost=ManaCost.parse("{4}{U}"))
        # Witherbloom + 2 bears = 3 creatures: {4}{U} -> {1}{U}
        set_board_state(
            game, 0, battlefield=[wb] + _bears(2), hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        cast_spell(game, 0, "Big Trick")
        assert game.get_graveyard(game.players[0]).contains(spell)

    def test_grant_reduces_generic_only(self):
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        spell = Instant(name="Pip Trick", mana_cost=ManaCost.parse("{1}{U}{U}"))
        set_board_state(
            game, 0, battlefield=[wb] + _bears(4), hand=[spell],
            mana={ManaType.BLUE: 1},
        )
        # 5 creatures, but only the {1} generic can be reduced — one {U}
        # in the pool is not enough for {U}{U}.
        with pytest.raises(TestSetupError):
            cast_spell(game, 0, "Pip Trick")
