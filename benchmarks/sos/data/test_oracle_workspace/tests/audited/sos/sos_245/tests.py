"""Rewritten audited tests for Witherbloom, the Balancer (sos_245).

Phase 18 convention: integration-style tests verifying observable behavior.

Tests:
1. Identity — name, mana_cost, P/T, types, supertypes, subtypes, colors.
2. Keywords — Flying + Deathtouch present as keyword flags.
3. Affinity reduces own cost — with N creatures, generic cost reduced by N.
4. Affinity clamps at generic (cannot go below 0 generic).
5. Affinity grant to instants/sorceries — controller's instants/sorceries
   get affinity for creatures when Witherbloom is on battlefield.
6. Grant does NOT apply to creature spells.
7. Grant does NOT apply to opponent's spells.
8. Grant removed when Witherbloom leaves the battlefield.
"""

from __future__ import annotations

import pytest

from card_impl import WitherbloomTheBalancer

from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    ManaType,
    Supertype,
    Zone,
)
from test_utils import (
    card_colors,
    create_game,
    set_battlefield,
)


# ---------------------------------------------------------------------------
# Test 1: Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    """Verify card identity — name, mana cost, stats, types, keywords."""

    def test_name_and_mana_cost(self) -> None:
        """Name is 'Witherbloom, the Balancer'; cost is {6}{B}{G} (CMC 8)."""
        card = WitherbloomTheBalancer()

        assert card.name == "Witherbloom, the Balancer"
        assert card.mana_cost.generic == 6
        assert card.mana_cost.pips[ManaType.BLACK] == 1
        assert card.mana_cost.pips[ManaType.GREEN] == 1
        assert card.mana_cost.cmc == 8

    def test_power_toughness(self) -> None:
        """5/5 body."""
        card = WitherbloomTheBalancer()
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_types_and_supertypes(self) -> None:
        """Legendary Creature — Elder Dragon."""
        card = WitherbloomTheBalancer()
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes

    def test_colors(self) -> None:
        """Black and Green (from mana cost)."""
        card = WitherbloomTheBalancer()
        assert card_colors(card) == {"B", "G"}


# ---------------------------------------------------------------------------
# Test 2: Keywords
# ---------------------------------------------------------------------------


class TestKeywords:
    """Verify Flying and Deathtouch as true keyword flags."""

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer()
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer()
        assert Keyword.DEATHTOUCH in card.keywords


# ---------------------------------------------------------------------------
# Test 3: Affinity reduces own cost
# ---------------------------------------------------------------------------


class TestAffinityReducesOwnCost:
    """Affinity for creatures — own casting cost reduced by creature count."""

    def test_reduction_equals_creature_count(self) -> None:
        """With 3 creatures on bf, cost_reduction returns 3."""
        game = create_game()
        player = game.players[0]

        tokens = [
            Creature(name=f"Token {i}", owner=player, base_power=1, base_toughness=1)
            for i in range(3)
        ]
        set_battlefield(game, 0, tokens)

        card = WitherbloomTheBalancer(owner=player)
        card.controller = player

        assert card.cost_reduction(game) == 3

    def test_no_creatures_no_reduction(self) -> None:
        """Empty battlefield → 0 reduction."""
        game = create_game()
        player = game.players[0]
        set_battlefield(game, 0, [])

        card = WitherbloomTheBalancer(owner=player)
        card.controller = player

        assert card.cost_reduction(game) == 0

    def test_reduction_clamped_to_generic(self) -> None:
        """get_cost_reduction clamps to generic portion (6) even with 10 creatures."""
        game = create_game()
        player = game.players[0]

        tokens = [
            Creature(name=f"Token {i}", owner=player, base_power=1, base_toughness=1)
            for i in range(10)
        ]
        set_battlefield(game, 0, tokens)

        card = WitherbloomTheBalancer(owner=player)
        reduction = get_cost_reduction(game, card, player)
        assert reduction == 6  # generic is 6, can't go below 0


# ---------------------------------------------------------------------------
# Test 4: Affinity grant to instants and sorceries
# ---------------------------------------------------------------------------


class TestAffinityGrantToInstantsAndSorceries:
    """Controller's instants/sorceries get affinity for creatures."""

    def test_instant_gets_reduction(self) -> None:
        """Instant gets cost reduced by creature count when Witherbloom on bf."""
        game = create_game()
        player = game.players[0]

        witherbloom = WitherbloomTheBalancer(owner=player)
        token1 = Creature(name="Token 1", owner=player, base_power=1, base_toughness=1)
        token2 = Creature(name="Token 2", owner=player, base_power=1, base_toughness=1)
        # Witherbloom itself is a creature — 3 total creatures
        set_battlefield(game, 0, [witherbloom, token1, token2])

        bolt = Instant(
            name="Expensive Bolt",
            mana_cost=ManaCost(generic=4, pips={ManaType.RED: 1}),
            owner=player,
        )

        reduction = get_cost_reduction(game, bolt, player)
        assert reduction == 3  # 3 creatures on bf

    def test_sorcery_gets_reduction(self) -> None:
        """Sorcery gets cost reduced by creature count when Witherbloom on bf."""
        game = create_game()
        player = game.players[0]

        witherbloom = WitherbloomTheBalancer(owner=player)
        token = Creature(name="Token", owner=player, base_power=1, base_toughness=1)
        set_battlefield(game, 0, [witherbloom, token])

        sorc = Sorcery(
            name="Big Sorcery",
            mana_cost=ManaCost(generic=5, pips={}),
            owner=player,
        )

        reduction = get_cost_reduction(game, sorc, player)
        assert reduction == 2  # 2 creatures (Witherbloom + token)


# ---------------------------------------------------------------------------
# Test 5: Grant does NOT apply to creature spells
# ---------------------------------------------------------------------------


class TestNoGrantToCreatureSpells:
    """Affinity grant only applies to instants/sorceries, not creatures."""

    def test_creature_spell_no_grant(self) -> None:
        """A creature spell does NOT benefit from the affinity grant."""
        game = create_game()
        player = game.players[0]

        witherbloom = WitherbloomTheBalancer(owner=player)
        token = Creature(name="Token", owner=player, base_power=1, base_toughness=1)
        set_battlefield(game, 0, [witherbloom, token])

        bear = Creature(
            name="Grizzly Bear",
            owner=player,
            base_power=2,
            base_toughness=2,
        )
        bear.mana_cost = ManaCost(generic=3, pips={})

        reduction = get_cost_reduction(game, bear, player)
        assert reduction == 0


# ---------------------------------------------------------------------------
# Test 6: Grant does NOT apply to opponent's spells
# ---------------------------------------------------------------------------


class TestNoGrantToOpponent:
    """Opponent's instants/sorceries do NOT get the affinity grant."""

    def test_opponent_instant_no_reduction(self) -> None:
        """Opponent's instants don't benefit from your Witherbloom."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        witherbloom = WitherbloomTheBalancer(owner=p1)
        token = Creature(name="Token", owner=p1, base_power=1, base_toughness=1)
        set_battlefield(game, 0, [witherbloom, token])

        # Opponent's instant
        opp_bolt = Instant(
            name="Opp Bolt",
            mana_cost=ManaCost(generic=3, pips={ManaType.RED: 1}),
            owner=p2,
        )

        # From opponent's perspective — they have no grant on THEIR bf
        reduction = get_cost_reduction(game, opp_bolt, p2)
        assert reduction == 0


# ---------------------------------------------------------------------------
# Test 7: Grant removed when Witherbloom leaves
# ---------------------------------------------------------------------------


class TestGrantRemovedWhenWitherbloomLeaves:
    """Once Witherbloom leaves bf, instants/sorceries lose affinity grant."""

    def test_removal_ends_grant(self) -> None:
        """After removing Witherbloom, instants no longer get cost reduction."""
        game = create_game()
        player = game.players[0]

        witherbloom = WitherbloomTheBalancer(owner=player)
        token = Creature(name="Token", owner=player, base_power=1, base_toughness=1)
        set_battlefield(game, 0, [witherbloom, token])

        bolt = Instant(
            name="Bolt",
            mana_cost=ManaCost(generic=3, pips={ManaType.RED: 1}),
            owner=player,
        )

        # With Witherbloom: 2 creatures → reduction 2
        assert get_cost_reduction(game, bolt, player) == 2

        # Remove Witherbloom from battlefield
        bf = player.zones[Zone.BATTLEFIELD]
        bf.remove(witherbloom)

        # Token still there but no granter → 0 reduction for instants
        assert get_cost_reduction(game, bolt, player) == 0
