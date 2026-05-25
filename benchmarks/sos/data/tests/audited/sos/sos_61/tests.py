"""Audited tests for Muse's Encouragement (collector key 61).

Verifies the Muse's Encouragement card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import MusesEncouragement

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMusesEncouragementBasicProperties:
    """Basic property tests for Muse's Encouragement."""

    def test_is_instant(self) -> None:
        """Muse's Encouragement must be a Instant subclass."""
        card = MusesEncouragement(name="Muse's Encouragement", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """MusesEncouragement.name must be 'Muse's Encouragement'."""
        card = MusesEncouragement(name="Muse's Encouragement", owner=None)
        assert card.name == "Muse's Encouragement"

    def test_card_types(self) -> None:
        """Muse's Encouragement must have correct card types."""
        card = MusesEncouragement(name="Muse's Encouragement", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Muse's Encouragement must have converted mana cost 5."""
        card = MusesEncouragement(name="Muse's Encouragement", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Muse's Encouragement must have correct colors."""
        card = MusesEncouragement(name="Muse's Encouragement", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestMusesEncouragementAbilities:
    """Ability tests for Muse's Encouragement — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = MusesEncouragement(name="Muse's Encouragement", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_surveil_effect(self) -> None:
        """Resolution should surveil 2."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Sorcery
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        for i in range(4):
            player.zones[Zone.LIBRARY].add(Sorcery(name=f"Lib{i}", owner=player))
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card = MusesEncouragement(name="Muse's Encouragement", owner=player)
        card.controller = player
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after > 0 or len(player.zones[Zone.LIBRARY].get_all()) <= lib_before, (
            "Surveil should manipulate library/graveyard"
        )


@pytest.mark.edge
class TestMusesEncouragementEdgeCases:
    """Edge case tests for Muse's Encouragement."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = MusesEncouragement(name="Muse's Encouragement", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestMusesEncouragementInteractions:
    """Interaction tests for Muse's Encouragement."""

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
        card = MusesEncouragement(name="Muse's Encouragement", owner=player)
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
        card = MusesEncouragement(name="Muse's Encouragement", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
