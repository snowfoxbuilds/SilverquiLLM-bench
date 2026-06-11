"""Tests for SOS 245 — Witherbloom, the Balancer (affinity self + grant via E3)."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, cast_spell, set_board_state


def _bears(n):
    return [Creature(name=f"Bear{i}", base_power=2, base_toughness=2) for i in range(n)]


class DummyInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Dummy")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)


class TestProperties:
    def test_basic(self):
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert card.base_power == 5 and card.base_toughness == 5
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestSelfAffinity:
    def test_three_creatures_reduce_generic(self):
        game = create_game()
        p0 = game.players[0]
        set_board_state(game, 0, battlefield=_bears(3))
        set_board_state(game, 0, hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        # {6}{B}{G} - 3 creatures = {3}{B}{G}: 3 colorless + B + G is exact.
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert any(getattr(c, "name", "") == "Witherbloom, the Balancer"
                   for c in game.get_battlefield(p0).get_all())

    def test_no_creatures_no_reduction(self):
        game = create_game()
        set_board_state(game, 0, hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 3, ManaType.BLACK: 1, ManaType.GREEN: 1})
        with pytest.raises(Exception):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_colored_pips_not_reduced(self):
        # Plenty of creatures, but the {B}{G} pips still must be paid.
        game = create_game()
        set_board_state(game, 0, battlefield=_bears(10))
        set_board_state(game, 0, hand=[WitherbloomTheBalancer(owner=None)],
                        mana={ManaType.COLORLESS: 2})  # no black/green
        with pytest.raises(Exception):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestGrantedAffinity:
    def test_instant_gets_affinity(self):
        game = create_game()
        p0 = game.players[0]
        wb = WitherbloomTheBalancer(owner=None)
        # Witherbloom + 2 bears = 3 creatures controlled.
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        set_board_state(game, 0, hand=[DummyInstant(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.RED: 1})
        # {4}{R} - 3 = {1}{R}: 1 colorless + R is exact.
        cast_spell(game, 0, "Dummy")
        assert game.get_graveyard(p0).contains(
            next(c for c in game.get_graveyard(p0).get_all() if c.name == "Dummy")
        )

    def test_without_witherbloom_no_grant(self):
        game = create_game()
        set_board_state(game, 0, battlefield=_bears(2))  # creatures but no granter
        set_board_state(game, 0, hand=[DummyInstant(owner=None)],
                        mana={ManaType.COLORLESS: 1, ManaType.RED: 1})
        with pytest.raises(Exception):
            cast_spell(game, 0, "Dummy")

    def test_grant_does_not_apply_to_creature_spells(self):
        # Witherbloom grants affinity only to instants/sorceries (E3 gate).
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        big = Creature(name="Big", mana_cost=ManaCost.parse("{4}{G}"),
                       base_power=4, base_toughness=4)
        set_board_state(game, 0, hand=[big],
                        mana={ManaType.COLORLESS: 1, ManaType.GREEN: 1})
        with pytest.raises(Exception):
            cast_spell(game, 0, "Big")
