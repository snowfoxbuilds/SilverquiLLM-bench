"""Audited tests for Spell Pierce (collector key soa_23).

Verifies the Spell Pierce card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SpellPierce

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSpellPierceBasicProperties:
    """Basic property tests for Spell Pierce."""

    def test_is_instant(self) -> None:
        """Spell Pierce must be a Instant subclass."""
        card = SpellPierce(name="Spell Pierce", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """SpellPierce.name must be 'Spell Pierce'."""
        card = SpellPierce(name="Spell Pierce", owner=None)
        assert card.name == "Spell Pierce"

    def test_card_types(self) -> None:
        """Spell Pierce must have correct card types."""
        card = SpellPierce(name="Spell Pierce", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Spell Pierce must have converted mana cost 1."""
        card = SpellPierce(name="Spell Pierce", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Spell Pierce must have correct colors."""
        card = SpellPierce(name="Spell Pierce", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestSpellPierceAbilities:
    """Ability tests for Spell Pierce — expected to fail against stubs."""

    def test_counters_spell(self) -> None:
        """Resolution should counter target spell."""
        from test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target_spell = Instant(name="Enemy", owner=opponent)
        target_spell.controller = opponent
        game.stack.append(target_spell)
        stack_before = len(game.stack)
        card = SpellPierce(name="Spell Pierce", owner=player)
        card.controller = player
        card._targets = [target_spell]
        if hasattr(card, "set_targets"):
            card.set_targets([target_spell])
        card.on_resolve(game)
        stack_after = len(game.stack)
        assert stack_after < stack_before, (
            f"Should counter: stack {stack_before} -> {stack_after}"
        )


@pytest.mark.edge
class TestSpellPierceEdgeCases:
    """Edge case tests for Spell Pierce."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SpellPierce(name="Spell Pierce", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestSpellPierceInteractions:
    """Interaction tests for Spell Pierce."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = SpellPierce(name="Spell Pierce", owner=player)
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
        card = SpellPierce(name="Spell Pierce", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
