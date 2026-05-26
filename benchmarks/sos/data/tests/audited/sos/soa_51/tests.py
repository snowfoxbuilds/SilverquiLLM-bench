"""Audited tests for Crop Rotation (collector key soa_51).

Verifies the Crop Rotation card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import CropRotation

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestCropRotationBasicProperties:
    """Basic property tests for Crop Rotation."""

    def test_is_instant(self) -> None:
        """Crop Rotation must be a Instant subclass."""
        card = CropRotation(name="Crop Rotation", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """CropRotation.name must be 'Crop Rotation'."""
        card = CropRotation(name="Crop Rotation", owner=None)
        assert card.name == "Crop Rotation"

    def test_card_types(self) -> None:
        """Crop Rotation must have correct card types."""
        card = CropRotation(name="Crop Rotation", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Crop Rotation must have converted mana cost 1."""
        card = CropRotation(name="Crop Rotation", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Crop Rotation must have correct colors."""
        card = CropRotation(name="Crop Rotation", owner=None)
        assert "G" in card_colors(card)

@pytest.mark.ability
class TestCropRotationAbilities:
    """Ability tests for Crop Rotation — expected to fail against stubs."""

    def test_additional_cost_declared(self) -> None:
        """Card must declare additional cost mechanism."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CropRotation(name="Crop Rotation", owner=player)
        card.controller = player
        has_addl = (
            hasattr(card, "additional_costs") or
            hasattr(card, "get_additional_costs") or
            (hasattr(card, "rules_text") and "additional cost" in (card.rules_text or "").lower())
        )
        assert has_addl, "Card must declare additional cost"

    def test_search_library(self) -> None:
        """Resolution should search library."""
        from test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(5):
            player.zones[Zone.LIBRARY].add(Sorcery(name=f"Lib{i}", owner=player))
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = CropRotation(name="Crop Rotation", owner=player)
        card.controller = player
        card.on_resolve(game)
        lib_after = len(player.zones[Zone.LIBRARY].get_all())
        assert lib_after < lib_before, (
            f"Should search library: {lib_before} -> {lib_after}"
        )

@pytest.mark.edge
class TestCropRotationEdgeCases:
    """Edge case tests for Crop Rotation."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CropRotation(name="Crop Rotation", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestCropRotationInteractions:
    """Interaction tests for Crop Rotation."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = CropRotation(name="Crop Rotation", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = CropRotation(name="Crop Rotation", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
