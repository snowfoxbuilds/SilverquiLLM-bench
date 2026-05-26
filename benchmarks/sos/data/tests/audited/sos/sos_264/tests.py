"""Audited tests for Sundown Pass (collector key 264).

Verifies the Sundown Pass card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import SundownPass

from engine.card import Land
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestSundownPassBasicProperties:
    """Basic property tests for Sundown Pass."""

    def test_is_land(self) -> None:
        """Sundown Pass must be a Land subclass."""
        card = SundownPass(name="Sundown Pass", owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        """SundownPass.name must be 'Sundown Pass'."""
        card = SundownPass(name="Sundown Pass", owner=None)
        assert card.name == "Sundown Pass"

    def test_card_types(self) -> None:
        """Sundown Pass must have correct card types."""
        card = SundownPass(name="Sundown Pass", owner=None)
        assert CardType.LAND in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Sundown Pass must have converted mana cost 0."""
        card = SundownPass(name="Sundown Pass", owner=None)
        assert card.mana_cost.cmc == 0

    def test_colors(self) -> None:
        """Sundown Pass must have correct colors."""
        card = SundownPass(name="Sundown Pass", owner=None)
        assert len(card_colors(card)) == 0

@pytest.mark.ability
class TestSundownPassAbilities:
    """Ability tests for Sundown Pass — expected to fail against stubs."""

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SundownPass(name="Sundown Pass", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"

@pytest.mark.edge
class TestSundownPassEdgeCases:
    """Edge case tests for Sundown Pass."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SundownPass(name="Sundown Pass", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestSundownPassInteractions:
    """Interaction tests for Sundown Pass."""

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
        card = SundownPass(name="Sundown Pass", owner=player)
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
        card = SundownPass(name="Sundown Pass", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
