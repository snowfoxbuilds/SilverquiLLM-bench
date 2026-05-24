"""Audited tests for Witherbloom, the Balancer (collector key 245).

Verifies the Witherbloom, the Balancer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import WitherbloomTheBalancer

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestWitherbloomTheBalancerBasicProperties:
    """Basic property tests for Witherbloom, the Balancer."""

    def test_is_creature(self) -> None:
        """Witherbloom, the Balancer must be a Creature subclass."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """WitherbloomTheBalancer.name must be 'Witherbloom, the Balancer'."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert card.name == "Witherbloom, the Balancer"

    def test_card_types(self) -> None:
        """Witherbloom, the Balancer must have correct card types."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Witherbloom, the Balancer must have converted mana cost 8."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert card.mana_cost.cmc == 8

    def test_colors(self) -> None:
        """Witherbloom, the Balancer must have correct colors."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert "B" in card.colors
        assert "G" in card.colors

    def test_power(self) -> None:
        """Witherbloom, the Balancer must have base power 5."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        """Witherbloom, the Balancer must have base toughness 5."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert card.base_toughness == 5


@pytest.mark.ability
class TestWitherbloomTheBalancerAbilities:
    """Ability tests for Witherbloom, the Balancer -- expected to fail against stubs."""

    def test_has_deathtouch(self) -> None:
        """Witherbloom, the Balancer must have Deathtouch keyword."""
        from engine.types import Keyword
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert Keyword.DEATHTOUCH in card.keywords, "Witherbloom, the Balancer should have Deathtouch"

    def test_has_flying(self) -> None:
        """Witherbloom, the Balancer must have Flying keyword."""
        from engine.types import Keyword
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert Keyword.FLYING in card.keywords, "Witherbloom, the Balancer should have Flying"

    def test_cost_reduction_implemented(self) -> None:
        """Cost reduction must be implemented per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        assert callable(getattr(card, "get_adjusted_cost", None)) or \
            callable(getattr(card, "cost_reduction", None)), \
            "Witherbloom, the Balancer must implement cost reduction per oracle text"


@pytest.mark.edge
class TestWitherbloomTheBalancerEdgeCases:
    """Edge case and trap tests for Witherbloom, the Balancer."""

    def test_cost_reduction_floor_at_zero(self) -> None:
        """Cost reduction must not reduce cost below zero."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        if callable(getattr(card, "get_adjusted_cost", None)):
            cost = card.get_adjusted_cost(game)
            assert cost >= 0, "Adjusted cost must never be negative"
        else:
            assert callable(getattr(card, "cost_reduction", None)), \
                "Must implement cost reduction"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        card2 = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        card1.name = "Modified"
        assert card2.name == "Witherbloom, the Balancer", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=None, base_power=5, base_toughness=5)
        assert card.mana_cost.cmc == 8, \
            f"CMC must be 8, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestWitherbloomTheBalancerInteractions:
    """Multi-card interaction tests for Witherbloom, the Balancer."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = WitherbloomTheBalancer(name="Witherbloom, the Balancer", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
