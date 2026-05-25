"""Audited tests for Duty Beyond Death (collector key soa_4).

Verifies the Duty Beyond Death card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import DutyBeyondDeath

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestDutyBeyondDeathBasicProperties:
    """Basic property tests for Duty Beyond Death."""

    def test_is_instant(self) -> None:
        """Duty Beyond Death must be a Instant subclass."""
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """DutyBeyondDeath.name must be 'Duty Beyond Death'."""
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=None)
        assert card.name == "Duty Beyond Death"

    def test_card_types(self) -> None:
        """Duty Beyond Death must have correct card types."""
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Duty Beyond Death must have converted mana cost 2."""
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Duty Beyond Death must have correct colors."""
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=None)
        assert "W" in card.colors


@pytest.mark.ability
class TestDutyBeyondDeathAbilities:
    """Ability tests for Duty Beyond Death — expected to fail against stubs."""

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=player)
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

    def test_grants_indestructible(self) -> None:
        """Resolution should grant indestructible."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.INDESTRUCTIBLE in target.keywords, (
            "Target should have indestructible after resolution"
        )

    def test_additional_cost_declared(self) -> None:
        """Card must declare additional cost mechanism."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=player)
        card.controller = player
        has_addl = (
            hasattr(card, "additional_costs") or
            hasattr(card, "get_additional_costs") or
            (hasattr(card, "rules_text") and "additional cost" in (card.rules_text or "").lower())
        )
        assert has_addl, "Card must declare additional cost"


@pytest.mark.edge
class TestDutyBeyondDeathEdgeCases:
    """Edge case tests for Duty Beyond Death."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestDutyBeyondDeathInteractions:
    """Interaction tests for Duty Beyond Death."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=player)
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
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = DutyBeyondDeath(name="Duty Beyond Death", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
