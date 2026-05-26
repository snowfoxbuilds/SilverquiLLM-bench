"""Audited tests for Dig Site Inventory (collector key 10).

Verifies the Dig Site Inventory card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import DigSiteInventory

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestDigSiteInventoryBasicProperties:
    """Basic property tests for Dig Site Inventory."""

    def test_is_sorcery(self) -> None:
        """Dig Site Inventory must be a Sorcery subclass."""
        card = DigSiteInventory(name="Dig Site Inventory", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """DigSiteInventory.name must be 'Dig Site Inventory'."""
        card = DigSiteInventory(name="Dig Site Inventory", owner=None)
        assert card.name == "Dig Site Inventory"

    def test_card_types(self) -> None:
        """Dig Site Inventory must have correct card types."""
        card = DigSiteInventory(name="Dig Site Inventory", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Dig Site Inventory must have converted mana cost 1."""
        card = DigSiteInventory(name="Dig Site Inventory", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Dig Site Inventory must have correct colors."""
        card = DigSiteInventory(name="Dig Site Inventory", owner=None)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestDigSiteInventoryAbilities:
    """Ability tests for Dig Site Inventory — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Dig Site Inventory must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert card in exile, "Card must be exiled after flashback resolution"

    def test_flashback_removes_from_graveyard(self) -> None:
        """Flashback resolution must remove card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        power_before = target.base_power
        card.on_resolve(game)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"+1/+1 counter: power {power_before} -> {power_after}"
        )

    def test_grants_vigilance(self) -> None:
        """Resolution should grant vigilance."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.VIGILANCE in target.keywords, (
            "Target should have vigilance after resolution"
        )

@pytest.mark.edge
class TestDigSiteInventoryEdgeCases:
    """Edge case tests for Dig Site Inventory."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"

@pytest.mark.interaction
class TestDigSiteInventoryInteractions:
    """Interaction tests for Dig Site Inventory."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = DigSiteInventory(name="Dig Site Inventory", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
