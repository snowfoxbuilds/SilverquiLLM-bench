"""Audited tests for Interjection (collector key 22).

Verifies the Interjection card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Interjection

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestInterjectionBasicProperties:
    """Basic property tests for Interjection."""

    def test_is_instant(self) -> None:
        """Interjection must be a Instant subclass."""
        card = Interjection(name="Interjection", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Interjection.name must be 'Interjection'."""
        card = Interjection(name="Interjection", owner=None)
        assert card.name == "Interjection"

    def test_card_types(self) -> None:
        """Interjection must have correct card types."""
        card = Interjection(name="Interjection", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Interjection must have converted mana cost 1."""
        card = Interjection(name="Interjection", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Interjection must have correct colors."""
        card = Interjection(name="Interjection", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestInterjectionAbilities:
    """Ability tests for Interjection — expected to fail against stubs."""

    def test_pump_effect(self) -> None:
        """Resolution should grant +2/+2."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="PumpTarget", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[target])
        card = Interjection(name="Interjection", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        actual_power = target.power if hasattr(target, "power") else target.base_power
        assert actual_power == 3, (
            f"Should pump to 3 power, got {actual_power}"
        )

    def test_grants_first_strike(self) -> None:
        """Resolution should grant first strike."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = Interjection(name="Interjection", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.FIRST_STRIKE in target.keywords, (
            "Target should have first strike after resolution"
        )


@pytest.mark.edge
class TestInterjectionEdgeCases:
    """Edge case tests for Interjection."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Interjection(name="Interjection", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestInterjectionInteractions:
    """Interaction tests for Interjection."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = Interjection(name="Interjection", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = Interjection(name="Interjection", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
