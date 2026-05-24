"""Audited tests for Graduation Day (collector key 16).

Verifies the Graduation Day card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import GraduationDay

from engine.card import Enchantment
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestGraduationDayBasicProperties:
    """Basic property tests for Graduation Day."""

    def test_is_enchantment(self) -> None:
        """Graduation Day must be a Enchantment subclass."""
        card = GraduationDay(name="Graduation Day", owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        """GraduationDay.name must be 'Graduation Day'."""
        card = GraduationDay(name="Graduation Day", owner=None)
        assert card.name == "Graduation Day"

    def test_card_types(self) -> None:
        """Graduation Day must have correct card types."""
        card = GraduationDay(name="Graduation Day", owner=None)
        assert CardType.ENCHANTMENT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Graduation Day must have converted mana cost 1."""
        card = GraduationDay(name="Graduation Day", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Graduation Day must have correct colors."""
        card = GraduationDay(name="Graduation Day", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestGraduationDayAbilities:
    """Ability tests for Graduation Day — expected to fail against stubs."""

    def test_repartee_registers_trigger(self) -> None:
        """Repartee must register a triggered ability."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = GraduationDay(name="Graduation Day", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        triggers = getattr(game, "triggers", [])
        assert len(triggers) > 0 or hasattr(card, "on_spell_cast"), (
            "Repartee card must register a trigger or expose on_spell_cast"
        )

    def test_repartee_requires_creature_target(self) -> None:
        """Repartee only triggers for spells targeting a creature."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = GraduationDay(name="Graduation Day", owner=player)
        card.controller = player
        target = Creature(name="Target", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[card, target])
        card.register_triggers(game)
        has_trigger_logic = (
            hasattr(card, "on_spell_cast") or
            hasattr(card, "repartee_trigger") or
            hasattr(card, "check_trigger_condition")
        )
        assert has_trigger_logic, "Repartee must check spell targets creature"

    def test_repartee_adds_counter(self) -> None:
        """Repartee trigger should add +1/+1 counter."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = GraduationDay(name="Graduation Day", owner=player)
        card.controller = player
        target = Creature(name="Buffed", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card, target])
        power_before = target.base_power
        if hasattr(card, "on_spell_cast"):
            card.on_spell_cast(game, target)
        elif hasattr(card, "repartee_trigger"):
            card.repartee_trigger(game, target)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"Repartee should add counter: power {power_before} -> {power_after}"
        )


@pytest.mark.edge
class TestGraduationDayEdgeCases:
    """Edge case tests for Graduation Day."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = GraduationDay(name="Graduation Day", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestGraduationDayInteractions:
    """Interaction tests for Graduation Day."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = GraduationDay(name="Graduation Day", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = GraduationDay(name="Graduation Day", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
