"""Audited tests for Bulk Up (collector key soa_40).

Verifies the Bulk Up card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import BulkUp

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBulkUpBasicProperties:
    """Basic property tests for Bulk Up."""

    def test_is_instant(self) -> None:
        """Bulk Up must be a Instant subclass."""
        card = BulkUp(name="Bulk Up", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """BulkUp.name must be 'Bulk Up'."""
        card = BulkUp(name="Bulk Up", owner=None)
        assert card.name == "Bulk Up"

    def test_card_types(self) -> None:
        """Bulk Up must have correct card types."""
        card = BulkUp(name="Bulk Up", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Bulk Up must have converted mana cost 2."""
        card = BulkUp(name="Bulk Up", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Bulk Up must have correct colors."""
        card = BulkUp(name="Bulk Up", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestBulkUpAbilities:
    """Ability tests for Bulk Up — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BulkUp(name="Bulk Up", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Bulk Up must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = BulkUp(name="Bulk Up", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert card in exile, "Card must be exiled after flashback resolution"

    def test_flashback_removes_from_graveyard(self) -> None:
        """Flashback resolution must remove card from graveyard."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = BulkUp(name="Bulk Up", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"


@pytest.mark.edge
class TestBulkUpEdgeCases:
    """Edge case tests for Bulk Up."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BulkUp(name="Bulk Up", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestBulkUpInteractions:
    """Interaction tests for Bulk Up."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = BulkUp(name="Bulk Up", owner=player)
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
        card = BulkUp(name="Bulk Up", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
