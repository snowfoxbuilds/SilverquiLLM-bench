"""Audited tests for Force of Will (collector key soa_19).

Verifies the Force of Will card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ForceOfWill

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestForceOfWillBasicProperties:
    """Basic property tests for Force of Will."""

    def test_is_instant(self) -> None:
        """Force of Will must be a Instant subclass."""
        card = ForceOfWill(name="Force of Will", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """ForceOfWill.name must be 'Force of Will'."""
        card = ForceOfWill(name="Force of Will", owner=None)
        assert card.name == "Force of Will"

    def test_card_types(self) -> None:
        """Force of Will must have correct card types."""
        card = ForceOfWill(name="Force of Will", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Force of Will must have converted mana cost 5."""
        card = ForceOfWill(name="Force of Will", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Force of Will must have correct colors."""
        card = ForceOfWill(name="Force of Will", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestForceOfWillAbilities:
    """Ability tests for Force of Will — expected to fail against stubs."""

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
        card = ForceOfWill(name="Force of Will", owner=player)
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
class TestForceOfWillEdgeCases:
    """Edge case tests for Force of Will."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ForceOfWill(name="Force of Will", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestForceOfWillInteractions:
    """Interaction tests for Force of Will."""

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
        card = ForceOfWill(name="Force of Will", owner=player)
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
        card = ForceOfWill(name="Force of Will", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
