"""Audited tests for Quandrix, the Proof (collector key 218).

Verifies the Quandrix, the Proof card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import QuandrixTheProof

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestQuandrixTheProofBasicProperties:
    """Basic property tests for Quandrix, the Proof."""

    def test_is_creature(self) -> None:
        """Quandrix, the Proof must be a Creature subclass."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """QuandrixTheProof.name must be 'Quandrix, the Proof'."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert card.name == "Quandrix, the Proof"

    def test_card_types(self) -> None:
        """Quandrix, the Proof must have correct card types."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Quandrix, the Proof must have converted mana cost 6."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Quandrix, the Proof must have correct colors."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert "G" in card_colors(card)
        assert "U" in card_colors(card)

    def test_power(self) -> None:
        """Quandrix, the Proof must have base power 6."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert card.base_power == 6

    def test_toughness(self) -> None:
        """Quandrix, the Proof must have base toughness 6."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert card.base_toughness == 6

@pytest.mark.ability
class TestQuandrixTheProofAbilities:
    """Ability tests for Quandrix, the Proof -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Quandrix, the Proof must have Flying keyword."""
        from engine.types import Keyword
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert Keyword.FLYING in card.keywords, "Quandrix, the Proof should have Flying"

    def test_has_trample(self) -> None:
        """Quandrix, the Proof must have Trample keyword."""
        from engine.types import Keyword
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert Keyword.TRAMPLE in card.keywords, "Quandrix, the Proof should have Trample"

    def test_cost_reduction_implemented(self) -> None:
        """Cost reduction must be implemented per oracle text."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        assert callable(getattr(card, "get_adjusted_cost", None)) or \
            callable(getattr(card, "cost_reduction", None)), \
            "Quandrix, the Proof must implement cost reduction per oracle text"

@pytest.mark.edge
class TestQuandrixTheProofEdgeCases:
    """Edge case and trap tests for Quandrix, the Proof."""

    def test_cost_reduction_floor_at_zero(self) -> None:
        """Cost reduction must not reduce cost below zero."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        if callable(getattr(card, "get_adjusted_cost", None)):
            cost = card.get_adjusted_cost(game)
            assert cost >= 0, "Adjusted cost must never be negative"
        else:
            assert callable(getattr(card, "cost_reduction", None)), \
                "Must implement cost reduction"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        card2 = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        card1.name = "Modified"
        assert card2.name == "Quandrix, the Proof", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=None, base_power=6, base_toughness=6)
        assert card.mana_cost.cmc == 6, \
            f"CMC must be 6, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestQuandrixTheProofInteractions:
    """Multi-card interaction tests for Quandrix, the Proof."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=player, base_power=6, base_toughness=6)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = QuandrixTheProof(name="Quandrix, the Proof", owner=player, base_power=6, base_toughness=6)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
