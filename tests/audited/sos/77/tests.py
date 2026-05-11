"""Audited tests for Cost of Brilliance (collector key 77).

Verifies the Cost of Brilliance card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import CostOfBrilliance

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestCostOfBrillianceBasicProperties:
    """Basic property tests for Cost of Brilliance."""

    def test_is_sorcery(self) -> None:
        """Cost of Brilliance must be a Sorcery subclass."""
        card = CostOfBrilliance(name="Cost of Brilliance", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """CostOfBrilliance.name must be 'Cost of Brilliance'."""
        card = CostOfBrilliance(name="Cost of Brilliance", owner=None)
        assert card.name == "Cost of Brilliance"

    def test_card_types(self) -> None:
        """Cost of Brilliance must have correct card types."""
        card = CostOfBrilliance(name="Cost of Brilliance", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Cost of Brilliance must have converted mana cost 3."""
        card = CostOfBrilliance(name="Cost of Brilliance", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Cost of Brilliance must have correct colors."""
        card = CostOfBrilliance(name="Cost of Brilliance", owner=None)
        assert "B" in card.colors


@pytest.mark.ability
class TestCostOfBrillianceAbilities:
    """Ability tests for Cost of Brilliance — expected to fail against stubs."""

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = CostOfBrilliance(name="Cost of Brilliance", owner=player)
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

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = CostOfBrilliance(name="Cost of Brilliance", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_causes_life_loss(self) -> None:
        """Resolution should cause life loss."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = CostOfBrilliance(name="Cost of Brilliance", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )


@pytest.mark.edge
class TestCostOfBrillianceEdgeCases:
    """Edge case tests for Cost of Brilliance."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CostOfBrilliance(name="Cost of Brilliance", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestCostOfBrillianceInteractions:
    """Interaction tests for Cost of Brilliance."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = CostOfBrilliance(name="Cost of Brilliance", owner=player)
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
        card = CostOfBrilliance(name="Cost of Brilliance", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
