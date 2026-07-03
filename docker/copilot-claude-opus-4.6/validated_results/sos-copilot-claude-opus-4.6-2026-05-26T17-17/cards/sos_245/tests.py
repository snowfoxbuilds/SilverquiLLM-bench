"""Tests for SOS 245 — Witherbloom, the Balancer.

Legendary Creature — Elder Dragon {6}{B}{G}
Affinity for creatures (This spell costs {1} less to cast for each creature you control.)
Flying, deathtouch
Instant and sorcery spells you cast have affinity for creatures.
5/5
"""

from __future__ import annotations

from cards.sos.sos_245.card_impl import WitherbloomTheBalancer
from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestWitherbloomTheBalancerProperties:
    """Static card data should match the SOS 245 spec."""

    def test_name(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.name == "Witherbloom, the Balancer"

    def test_mana_cost(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.mana_cost == ManaCost.parse("{6}{B}{G}")

    def test_power_toughness(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert card.base_power == 5
        assert card.base_toughness == 5

    def test_is_creature(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert isinstance(card, Creature)

    def test_has_flying(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_deathtouch(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_legendary(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        from engine.types import Supertype
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_elder_dragon(self) -> None:
        card = WitherbloomTheBalancer(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


class TestWitherbloomTheBalancerAffinity:
    """Affinity for creatures: costs {1} less per creature you control."""

    def test_affinity_reduces_cost_by_creature_count(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Place 3 creatures on battlefield
        creatures = [
            Creature(name=f"Token {i}", base_power=1, base_toughness=1)
            for i in range(3)
        ]
        for c in creatures:
            c.owner = p1
            c.controller = p1
        set_board_state(game, 0, battlefield=creatures)
        effective_cost = card.get_effective_cost(game)
        # {6}{B}{G} minus 3 generic = {3}{B}{G}
        expected = ManaCost.parse("{3}{B}{G}")
        assert effective_cost == expected

    def test_affinity_cannot_reduce_below_colored(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        # Place 8 creatures — more than the generic portion
        creatures = [
            Creature(name=f"Token {i}", base_power=1, base_toughness=1)
            for i in range(8)
        ]
        for c in creatures:
            c.owner = p1
            c.controller = p1
        set_board_state(game, 0, battlefield=creatures)
        effective_cost = card.get_effective_cost(game)
        # Cannot reduce below {B}{G}
        expected = ManaCost.parse("{B}{G}")
        assert effective_cost == expected

    def test_no_creatures_no_reduction(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        effective_cost = card.get_effective_cost(game)
        expected = ManaCost.parse("{6}{B}{G}")
        assert effective_cost == expected


class TestWitherbloomGrantsAffinity:
    """Instant and sorcery spells you cast have affinity for creatures."""

    def test_grants_affinity_to_instant_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[witherbloom])
        # Create a generic instant with cost {3}{R}
        from engine.card import Instant
        spell = Instant(name="Bolt Plus", owner=p1, controller=p1)
        spell.mana_cost = ManaCost.parse("{3}{R}")
        # Add 2 creatures to battlefield (Witherbloom itself counts)
        extra = Creature(name="Helper", base_power=1, base_toughness=1)
        extra.owner = p1
        extra.controller = p1
        set_board_state(game, 0, battlefield=[witherbloom, extra])
        # The spell should benefit from affinity for creatures (2 creatures)
        effective_cost = spell.get_effective_cost(game)
        expected = ManaCost.parse("{1}{R}")
        assert effective_cost == expected

    def test_does_not_grant_affinity_to_creature_spells(self) -> None:
        """Only instants and sorceries get affinity, not creature spells."""
        game = create_game()
        p1 = game.players[0]
        witherbloom = WitherbloomTheBalancer(owner=p1, controller=p1)
        other_creature = Creature(name="Bear", base_power=2, base_toughness=2)
        other_creature.owner = p1
        other_creature.controller = p1
        other_creature.mana_cost = ManaCost.parse("{3}{G}")
        set_board_state(game, 0, battlefield=[witherbloom])
        # The creature spell should NOT benefit from Witherbloom's granted affinity
        effective_cost = other_creature.get_effective_cost(game)
        expected = ManaCost.parse("{3}{G}")
        assert effective_cost == expected
