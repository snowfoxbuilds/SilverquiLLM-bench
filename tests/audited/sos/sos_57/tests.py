"""Audited tests for Mana Sculpt (collector key 57).

Verifies the Mana Sculpt card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ManaSculpt

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestManaSculptBasicProperties:
    """Basic property tests for Mana Sculpt."""

    def test_is_instant(self) -> None:
        """Mana Sculpt must be a Instant subclass."""
        card = ManaSculpt(name="Mana Sculpt", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """ManaSculpt.name must be 'Mana Sculpt'."""
        card = ManaSculpt(name="Mana Sculpt", owner=None)
        assert card.name == "Mana Sculpt"

    def test_card_types(self) -> None:
        """Mana Sculpt must have correct card types."""
        card = ManaSculpt(name="Mana Sculpt", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Mana Sculpt must have converted mana cost 3."""
        card = ManaSculpt(name="Mana Sculpt", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Mana Sculpt must have correct colors."""
        card = ManaSculpt(name="Mana Sculpt", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestManaSculptAbilities:
    """Ability tests for Mana Sculpt — expected to fail against stubs."""

    def test_counters_spell(self) -> None:
        """Resolution should counter target spell."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target_spell = Instant(name="Enemy", owner=opponent)
        target_spell.controller = opponent
        game.stack.append(target_spell)
        stack_before = len(game.stack)
        card = ManaSculpt(name="Mana Sculpt", owner=player)
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
class TestManaSculptEdgeCases:
    """Edge case tests for Mana Sculpt."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = ManaSculpt(name="Mana Sculpt", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestManaSculptInteractions:
    """Interaction tests for Mana Sculpt."""

    def test_get_targets_finds_stack_spells(self) -> None:
        """get_targets should find spells on stack."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from benchmarks.sos.workspace.engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        spell = Instant(name="OnStack", owner=opponent)
        spell.controller = opponent
        game.stack.append(spell)
        card = ManaSculpt(name="Mana Sculpt", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find spell on stack"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = ManaSculpt(name="Mana Sculpt", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
