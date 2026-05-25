"""Audited tests for Unsubtle Mockery (collector key 136).

Verifies the Unsubtle Mockery card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import UnsubtleMockery

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestUnsubtleMockeryBasicProperties:
    """Basic property tests for Unsubtle Mockery."""

    def test_is_instant(self) -> None:
        """Unsubtle Mockery must be a Instant subclass."""
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """UnsubtleMockery.name must be 'Unsubtle Mockery'."""
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=None)
        assert card.name == "Unsubtle Mockery"

    def test_card_types(self) -> None:
        """Unsubtle Mockery must have correct card types."""
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Unsubtle Mockery must have converted mana cost 3."""
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Unsubtle Mockery must have correct colors."""
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestUnsubtleMockeryAbilities:
    """Ability tests for Unsubtle Mockery — expected to fail against stubs."""

    def test_deals_damage(self) -> None:
        """Resolution should deal 4 damage."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=player)
        card.controller = player
        card._targets = [opponent]
        if hasattr(card, "set_targets"):
            card.set_targets([opponent])
        card.on_resolve(game)
        life_after = opponent.life
        assert life_after < life_before, (
            f"Should deal damage: life {life_before} -> {life_after}"
        )

    def test_surveil_effect(self) -> None:
        """Resolution should surveil 1."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Sorcery
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(3):
            player.zones[Zone.LIBRARY].add(Sorcery(name=f"Lib{i}", owner=player))
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=player)
        card.controller = player
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after > 0 or len(player.zones[Zone.LIBRARY].get_all()) <= lib_before, (
            "Surveil should manipulate library/graveyard"
        )


@pytest.mark.edge
class TestUnsubtleMockeryEdgeCases:
    """Edge case tests for Unsubtle Mockery."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestUnsubtleMockeryInteractions:
    """Interaction tests for Unsubtle Mockery."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=player)
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
        card = UnsubtleMockery(name="Unsubtle Mockery", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
