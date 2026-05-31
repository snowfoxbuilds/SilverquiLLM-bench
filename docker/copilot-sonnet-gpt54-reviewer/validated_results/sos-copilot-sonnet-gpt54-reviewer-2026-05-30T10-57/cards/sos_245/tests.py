"""Tests for sos_245 — Witherbloom, the Balancer."""
from __future__ import annotations

import pytest

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype
from test_utils import create_game


class TestWitherbloomProperties:
    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Witherbloom" in card.name

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_legendary_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes


class TestWitherbloomCostReduction:
    """Affinity for creatures: costs {1} less for each creature you control."""

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        # No creatures on battlefield.
        assert dragon.cost_reduction(game) == 0

    def test_cost_reduction_with_one_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)
        # Dragon itself is on battlefield.
        assert dragon.cost_reduction(game) >= 1

    def test_cost_reduction_with_multiple_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)
        other = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        game.get_battlefield(p1).add(other)
        assert dragon.cost_reduction(game) == 2

    def test_cost_reduction_does_not_count_opponent_creatures(self) -> None:
        game = create_game()
        p1, p2 = game.players
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)
        opp_creature = Creature(name="Goblin", base_power=1, base_toughness=1, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_creature)
        # Only count controller's creatures.
        assert dragon.cost_reduction(game) == 1


class TestWitherbloomSpellAffinity:
    """Instant and sorcery spells you cast also have affinity for creatures."""

    def test_grants_affinity_to_instant(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)
        instant = Instant(name="Shock", mana_cost=ManaCost.parse("{R}"), owner=p1, controller=p1)
        reduction = dragon.get_spell_cost_reduction(game, instant)
        assert reduction >= 1  # 1 creature (dragon) on battlefield

    def test_grants_affinity_to_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)
        sorcery = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"), owner=p1, controller=p1)
        reduction = dragon.get_spell_cost_reduction(game, sorcery)
        assert reduction >= 1

    def test_no_affinity_for_creature_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        dragon = WitherbloomTheBalancer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(dragon)
        creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1)
        reduction = dragon.get_spell_cost_reduction(game, creature)
        assert reduction == 0
