"""Audited tests for Bitter Triumph (collector key soa_26).

Verifies the Bitter Triumph card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import BitterTriumph

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBitterTriumphBasicProperties:
    """Basic property tests for Bitter Triumph."""

    def test_is_instant(self) -> None:
        """Bitter Triumph must be a Instant subclass."""
        card = BitterTriumph(name="Bitter Triumph", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """BitterTriumph.name must be 'Bitter Triumph'."""
        card = BitterTriumph(name="Bitter Triumph", owner=None)
        assert card.name == "Bitter Triumph"

    def test_card_types(self) -> None:
        """Bitter Triumph must have correct card types."""
        card = BitterTriumph(name="Bitter Triumph", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Bitter Triumph must have converted mana cost 2."""
        card = BitterTriumph(name="Bitter Triumph", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Bitter Triumph must have correct colors."""
        card = BitterTriumph(name="Bitter Triumph", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestBitterTriumphAbilities:
    """Ability tests for Bitter Triumph — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = BitterTriumph(name="Bitter Triumph", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        bf_before = len(game.get_battlefield(opponent).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(opponent).get_all())
        assert bf_after < bf_before, (
            f"Target should be destroyed: bf {bf_before} -> {bf_after}"
        )

    def test_causes_discard(self) -> None:
        """Resolution should cause discard."""
        from test_utils import create_game, set_board_state
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        filler = Sorcery(name="Discardable", owner=opponent)
        set_board_state(game, 1, hand=[filler])
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = BitterTriumph(name="Bitter Triumph", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_additional_cost_declared(self) -> None:
        """Card must declare additional cost mechanism."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BitterTriumph(name="Bitter Triumph", owner=player)
        card.controller = player
        has_addl = (
            hasattr(card, "additional_costs") or
            hasattr(card, "get_additional_costs") or
            (hasattr(card, "rules_text") and "additional cost" in (card.rules_text or "").lower())
        )
        assert has_addl, "Card must declare additional cost"


@pytest.mark.edge
class TestBitterTriumphEdgeCases:
    """Edge case tests for Bitter Triumph."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BitterTriumph(name="Bitter Triumph", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestBitterTriumphInteractions:
    """Interaction tests for Bitter Triumph."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = BitterTriumph(name="Bitter Triumph", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = BitterTriumph(name="Bitter Triumph", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
