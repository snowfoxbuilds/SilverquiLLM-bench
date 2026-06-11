"""Tests for SOS 245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import TestSetupError as SetupError
from test_utils import cast_spell, create_game, set_board_state


def _bears(n: int) -> list[Creature]:
    return [
        Creature(name=f"Bear{i}", base_power=2, base_toughness=2)
        for i in range(n)
    ]


class TestWitherbloomProperties:
    def test_static_data(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert {"Elder", "Dragon"} <= card.subtypes
        assert card.base_power == 5 and card.base_toughness == 5


class TestOwnAffinity:
    def test_costs_one_less_per_creature_you_control(self) -> None:
        game = create_game()
        set_board_state(
            game, 0,
            battlefield=_bears(3),
            hand=[WitherbloomTheBalancer(owner=None)],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        cast_spell(game, 0, "Witherbloom, the Balancer")
        bf_names = [c.name for c in game.players[0].zones[Zone.BATTLEFIELD].get_all()]
        assert "Witherbloom, the Balancer" in bf_names
        assert game.players[0].mana_pool.total() == 0

    def test_no_creatures_full_price(self) -> None:
        game = create_game()
        set_board_state(
            game, 0,
            hand=[WitherbloomTheBalancer(owner=None)],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 5},
        )
        with pytest.raises(SetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")

    def test_opponents_creatures_do_not_count(self) -> None:
        game = create_game()
        set_board_state(
            game, 0,
            hand=[WitherbloomTheBalancer(owner=None)],
            mana={ManaType.BLACK: 1, ManaType.GREEN: 1, ManaType.COLORLESS: 3},
        )
        set_board_state(game, 1, battlefield=_bears(3))
        with pytest.raises(SetupError):
            cast_spell(game, 0, "Witherbloom, the Balancer")


class TestGrantedAffinity:
    def test_your_instants_get_affinity_for_creatures(self) -> None:
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{4}{R}"))
        # Witherbloom itself plus two bears = 3 creatures.
        set_board_state(
            game, 0,
            battlefield=[wb] + _bears(2),
            hand=[probe],
            mana={ManaType.RED: 1, ManaType.COLORLESS: 1},
        )
        # {4}{R} - 3 = {1}{R}
        cast_spell(game, 0, "Probe")
        assert game.players[0].mana_pool.total() == 0

    def test_affinity_never_reduces_colored_pips(self) -> None:
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{R}{R}"))
        set_board_state(
            game, 0,
            battlefield=[wb] + _bears(4),
            hand=[probe],
            mana={ManaType.RED: 1},
        )
        with pytest.raises(SetupError):
            cast_spell(game, 0, "Probe")

    def test_creature_spells_do_not_get_the_grant(self) -> None:
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        bear_card = Creature(
            name="HandBear", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{3}{G}"),
        )
        set_board_state(
            game, 0,
            battlefield=[wb] + _bears(2),
            hand=[bear_card],
            mana={ManaType.GREEN: 1},
        )
        with pytest.raises(SetupError):
            cast_spell(game, 0, "HandBear")

    def test_opponent_spells_do_not_get_the_grant(self) -> None:
        game = create_game()
        wb = WitherbloomTheBalancer(owner=None)
        probe = Instant(name="Probe", mana_cost=ManaCost.parse("{2}{R}"))
        set_board_state(game, 0, battlefield=[wb] + _bears(2))
        set_board_state(game, 1, hand=[probe], mana={ManaType.RED: 1})
        with pytest.raises(SetupError):
            cast_spell(game, 1, "Probe")
