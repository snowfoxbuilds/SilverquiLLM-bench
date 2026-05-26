"""Audited tests for Daze (collector key soa_15).

Verifies the Daze card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import Daze

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestDazeBasicProperties:
    """Basic property tests for Daze."""

    def test_is_instant(self) -> None:
        """Daze must be a Instant subclass."""
        card = Daze(name="Daze", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Daze.name must be 'Daze'."""
        card = Daze(name="Daze", owner=None)
        assert card.name == "Daze"

    def test_card_types(self) -> None:
        """Daze must have correct card types."""
        card = Daze(name="Daze", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Daze must have converted mana cost 2."""
        card = Daze(name="Daze", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Daze must have correct colors."""
        card = Daze(name="Daze", owner=None)
        assert "U" in card_colors(card)

@pytest.mark.ability
class TestDazeAbilities:
    """Ability tests for Daze — expected to fail against stubs."""

    def test_counters_spell(self) -> None:
        """Resolution should counter target spell."""
        from test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        from engine.stack import StackObject
        from engine.types import Zone
        target_spell = Instant(name="Enemy", owner=opponent)
        target_spell.controller = opponent
        target_stack_obj = StackObject(source=target_spell, controller=opponent)
        game.stack.push(target_stack_obj)
        opponent.zones[Zone.STACK].add(target_spell)
        stack_before = len(game.stack)
        card = Daze(name="Daze", owner=player)
        card.controller = player
        card.chosen_targets = [target_stack_obj]
        card.on_resolve(game)
        stack_after = len(game.stack)
        assert stack_after < stack_before, (
            f"Should counter: stack {stack_before} -> {stack_after}"
        )

    def test_bounces_target(self) -> None:
        """Resolution should return target to hand."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Bounced", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = Daze(name="Daze", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        bf_before = len(game.get_battlefield(opponent).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(opponent).get_all())
        assert bf_after < bf_before, (
            f"Target should leave bf: {bf_before} -> {bf_after}"
        )

@pytest.mark.edge
class TestDazeEdgeCases:
    """Edge case tests for Daze."""

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
        card = Daze(name="Daze", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"

@pytest.mark.interaction
class TestDazeInteractions:
    """Interaction tests for Daze."""

    def test_get_targets_finds_stack_spells(self) -> None:
        """get_targets should find spells on stack."""
        from test_utils import create_game
        from engine.card import Instant
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        from engine.stack import StackObject
        from engine.types import Zone
        spell = Instant(name="OnStack", owner=opponent)
        spell.controller = opponent
        stack_obj = StackObject(source=spell, controller=opponent)
        game.stack.push(stack_obj)
        opponent.zones[Zone.STACK].add(spell)
        card = Daze(name="Daze", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find spell on stack"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = Daze(name="Daze", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
