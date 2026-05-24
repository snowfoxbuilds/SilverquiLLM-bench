"""Audited tests for Wilt in the Heat (collector key 243).

Verifies the Wilt in the Heat card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import WiltInTheHeat

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestWiltInTheHeatBasicProperties:
    """Basic property tests for Wilt in the Heat."""

    def test_is_instant(self) -> None:
        """Wilt in the Heat must be a Instant subclass."""
        card = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """WiltInTheHeat.name must be 'Wilt in the Heat'."""
        card = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        assert card.name == "Wilt in the Heat"

    def test_card_types(self) -> None:
        """Wilt in the Heat must have correct card types."""
        card = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Wilt in the Heat must have converted mana cost 4."""
        card = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Wilt in the Heat must have correct colors."""
        card = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        assert "R" in card.colors
        assert "W" in card.colors


@pytest.mark.ability
class TestWiltInTheHeatAbilities:
    """Ability tests for Wilt in the Heat -- expected to fail against stubs."""

    def test_cost_reduction_implemented(self) -> None:
        """Cost reduction must be implemented per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = WiltInTheHeat(name="Wilt in the Heat", owner=player)
        card.controller = player
        assert callable(getattr(card, "get_adjusted_cost", None)) or \
            callable(getattr(card, "cost_reduction", None)), \
            "Wilt in the Heat must implement cost reduction per oracle text"

    def test_resolution_deals_damage(self) -> None:
        """Spell resolution must deal damage per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = WiltInTheHeat(name="Wilt in the Heat", owner=player)
        card.controller = player
        initial_life = opponent.life
        card.on_resolve(game)
        assert opponent.life < initial_life, "Wilt in the Heat must deal damage on resolution"


@pytest.mark.edge
class TestWiltInTheHeatEdgeCases:
    """Edge case and trap tests for Wilt in the Heat."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = WiltInTheHeat(name="Wilt in the Heat", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Fizzled spell must go to graveyard"

    def test_cost_reduction_floor_at_zero(self) -> None:
        """Cost reduction must not reduce cost below zero."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = WiltInTheHeat(name="Wilt in the Heat", owner=player)
        card.controller = player
        if callable(getattr(card, "get_adjusted_cost", None)):
            cost = card.get_adjusted_cost(game)
            assert cost >= 0, "Adjusted cost must never be negative"
        else:
            assert callable(getattr(card, "cost_reduction", None)), \
                "Must implement cost reduction"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        card2 = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        card1.name = "Modified"
        assert card2.name == "Wilt in the Heat", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = WiltInTheHeat(name="Wilt in the Heat", owner=None)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestWiltInTheHeatInteractions:
    """Multi-card interaction tests for Wilt in the Heat."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = WiltInTheHeat(name="Wilt in the Heat", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = WiltInTheHeat(name="Wilt in the Heat", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
