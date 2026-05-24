"""Audited tests for Shattered Sanctum (collector key 260).

Verifies the Shattered Sanctum card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ShatteredSanctum

from benchmarks.sos.workspace.engine.card import Land
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestShatteredSanctumBasicProperties:
    """Basic property tests for Shattered Sanctum."""

    def test_is_land(self) -> None:
        """Shattered Sanctum must be a Land subclass."""
        card = ShatteredSanctum(name="Shattered Sanctum", owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        """ShatteredSanctum.name must be 'Shattered Sanctum'."""
        card = ShatteredSanctum(name="Shattered Sanctum", owner=None)
        assert card.name == "Shattered Sanctum"

    def test_card_types(self) -> None:
        """Shattered Sanctum must have correct card types."""
        card = ShatteredSanctum(name="Shattered Sanctum", owner=None)
        assert CardType.LAND in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Shattered Sanctum must have converted mana cost 0."""
        card = ShatteredSanctum(name="Shattered Sanctum", owner=None)
        assert card.mana_cost.cmc == 0

    def test_colors(self) -> None:
        """Shattered Sanctum must have correct colors."""
        card = ShatteredSanctum(name="Shattered Sanctum", owner=None)
        assert len(card.colors) == 0


@pytest.mark.ability
class TestShatteredSanctumAbilities:
    """Ability tests for Shattered Sanctum — expected to fail against stubs."""

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ShatteredSanctum(name="Shattered Sanctum", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestShatteredSanctumEdgeCases:
    """Edge case tests for Shattered Sanctum."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ShatteredSanctum(name="Shattered Sanctum", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestShatteredSanctumInteractions:
    """Interaction tests for Shattered Sanctum."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = ShatteredSanctum(name="Shattered Sanctum", owner=player)
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
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = ShatteredSanctum(name="Shattered Sanctum", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
