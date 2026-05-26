"""Audited tests for Berserk (collector key soa_50).

Verifies the Berserk card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import Berserk

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestBerserkBasicProperties:
    """Basic property tests for Berserk."""

    def test_is_instant(self) -> None:
        """Berserk must be a Instant subclass."""
        card = Berserk(name="Berserk", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Berserk.name must be 'Berserk'."""
        card = Berserk(name="Berserk", owner=None)
        assert card.name == "Berserk"

    def test_card_types(self) -> None:
        """Berserk must have correct card types."""
        card = Berserk(name="Berserk", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Berserk must have converted mana cost 1."""
        card = Berserk(name="Berserk", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Berserk must have correct colors."""
        card = Berserk(name="Berserk", owner=None)
        assert "G" in card_colors(card)

@pytest.mark.ability
class TestBerserkAbilities:
    """Ability tests for Berserk — expected to fail against stubs."""

    def test_grants_trample(self) -> None:
        """Resolution should grant trample."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = Berserk(name="Berserk", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.TRAMPLE in target.keywords, (
            "Target should have trample after resolution"
        )

@pytest.mark.edge
class TestBerserkEdgeCases:
    """Edge case tests for Berserk."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Berserk(name="Berserk", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestBerserkInteractions:
    """Interaction tests for Berserk."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = Berserk(name="Berserk", owner=player)
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
        card = Berserk(name="Berserk", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
