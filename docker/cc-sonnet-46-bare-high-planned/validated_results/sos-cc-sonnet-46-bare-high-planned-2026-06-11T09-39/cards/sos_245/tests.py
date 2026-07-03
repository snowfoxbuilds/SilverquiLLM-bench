"""Tests for sos_245 — Witherbloom, the Balancer."""

from __future__ import annotations

import pytest
from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestWitherbloomProperties:
    def test_name(self) -> None:
        assert WitherbloomTheBalancer().name == "Witherbloom, the Balancer"

    def test_flying_deathtouch(self) -> None:
        card = WitherbloomTheBalancer()
        assert Keyword.FLYING in card.keywords
        assert Keyword.DEATHTOUCH in card.keywords

    def test_stats(self) -> None:
        card = WitherbloomTheBalancer()
        assert card.base_power == 5
        assert card.base_toughness == 5


class TestWitherbloomAffinity:
    def test_self_affinity_no_creatures(self) -> None:
        """No creatures on board → no cost reduction for self."""
        game = create_game()
        p0 = game.players[0]
        card = WitherbloomTheBalancer()
        card.controller = p0
        assert card.cost_reduction(game) == 0

    def test_self_affinity_with_creatures(self) -> None:
        """3 creatures on board → cost reduction of 3."""
        game = create_game()
        p0 = game.players[0]
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        c3 = Creature(name="C3", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[c1, c2, c3])
        card = WitherbloomTheBalancer()
        card.controller = p0
        assert card.cost_reduction(game) == 3

    def test_cast_self_with_reduction(self) -> None:
        """Witherbloom costs 2 less with 2 creatures — {6}{B}{G} → {4}{B}{G}."""
        game = create_game()
        p0 = game.players[0]
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[c1, c2])
        w = WitherbloomTheBalancer()
        # {4}{B}{G} = 4 generic + 1 black + 1 green = 6 total
        set_board_state(game, 0, hand=[w], mana={ManaType.COLORLESS: 4, ManaType.BLACK: 1, ManaType.GREEN: 1})
        cast_spell(game, 0, "Witherbloom, the Balancer")
        assert game.get_battlefield(p0).contains(w)

    def test_spell_affinity_grants_reduction_to_instant(self) -> None:
        """With Witherbloom on battlefield, instants get affinity for creatures."""
        game = create_game()
        p0 = game.players[0]
        w = WitherbloomTheBalancer()
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[w, c1])
        # Instant costs {3} generic; should be reduced by 2 (c1 + w = 2 creatures)
        instant = Instant(name="Costly", mana_cost=ManaCost(generic=3))
        instant.controller = p0
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, instant, p0)
        assert reduction == 2  # 2 creatures: w and c1

    def test_spell_affinity_does_not_apply_to_opponent(self) -> None:
        """Witherbloom only grants affinity to its controller's spells."""
        game = create_game()
        p0 = game.players[0]
        p1 = game.players[1]
        w = WitherbloomTheBalancer()
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[w, c1])
        # Opponent's instant should not benefit from Witherbloom
        opp_instant = Instant(name="Bolt", mana_cost=ManaCost(generic=3))
        opp_instant.controller = p1
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, opp_instant, p1)
        assert reduction == 0
