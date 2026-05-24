"""Audited tests for Duel Tactics (collector key 112).

Verifies the Duel Tactics card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import DuelTactics

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDuelTacticsBasicProperties:
    """Basic property tests for Duel Tactics."""

    def test_is_sorcery(self) -> None:
        """Duel Tactics must be a Sorcery subclass."""
        card = DuelTactics(name="Duel Tactics", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """DuelTactics.name must be 'Duel Tactics'."""
        card = DuelTactics(name="Duel Tactics", owner=None)
        assert card.name == "Duel Tactics"

    def test_card_types(self) -> None:
        """Duel Tactics must have correct card types."""
        card = DuelTactics(name="Duel Tactics", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Duel Tactics must have converted mana cost 1."""
        card = DuelTactics(name="Duel Tactics", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Duel Tactics must have correct colors."""
        card = DuelTactics(name="Duel Tactics", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestDuelTacticsAbilities:
    """Ability tests for Duel Tactics — expected to fail against stubs."""

    def test_flashback_cost_attribute(self) -> None:
        """Card must expose a flashback cost distinct from normal mana cost."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DuelTactics(name="Duel Tactics", owner=player)
        card.controller = player
        has_fb = hasattr(card, "flashback_cost") or hasattr(card, "alternate_costs")
        assert has_fb, "Duel Tactics must expose flashback cost"

    def test_flashback_exiles_after_resolution(self) -> None:
        """Card must be exiled after flashback resolution."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = DuelTactics(name="Duel Tactics", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        exile = player.zones[Zone.EXILE].get_all()
        assert card in exile, "Card must be exiled after flashback resolution"

    def test_flashback_removes_from_graveyard(self) -> None:
        """Flashback resolution must remove card from graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = DuelTactics(name="Duel Tactics", owner=player)
        card.controller = player
        set_board_state(game, 0, graveyard=[card])
        assert card in player.zones[Zone.GRAVEYARD].get_all()
        if hasattr(card, "_cast_via_flashback"):
            card._cast_via_flashback = True
        card.on_resolve(game)
        gy_after = player.zones[Zone.GRAVEYARD].get_all()
        assert card not in gy_after, "Card must leave graveyard after flashback"

    def test_deals_damage(self) -> None:
        """Resolution should deal 1 damage."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = DuelTactics(name="Duel Tactics", owner=player)
        card.controller = player
        card._targets = [opponent]
        if hasattr(card, "set_targets"):
            card.set_targets([opponent])
        card.on_resolve(game)
        life_after = opponent.life
        assert life_after < life_before, (
            f"Should deal damage: life {life_before} -> {life_after}"
        )


@pytest.mark.edge
class TestDuelTacticsEdgeCases:
    """Edge case tests for Duel Tactics."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DuelTactics(name="Duel Tactics", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestDuelTacticsInteractions:
    """Interaction tests for Duel Tactics."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = DuelTactics(name="Duel Tactics", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = DuelTactics(name="Duel Tactics", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
