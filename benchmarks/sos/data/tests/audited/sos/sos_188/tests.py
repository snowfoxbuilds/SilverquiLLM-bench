"""Audited tests for Fix What's Broken (collector key 188).

Verifies the Fix What's Broken card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import FixWhatsBroken

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestFixWhatsBrokenBasicProperties:
    """Basic property tests for Fix What's Broken."""

    def test_is_sorcery(self) -> None:
        """Fix What's Broken must be a Sorcery subclass."""
        card = FixWhatsBroken(name="Fix What's Broken", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """FixWhatsBroken.name must be 'Fix What's Broken'."""
        card = FixWhatsBroken(name="Fix What's Broken", owner=None)
        assert card.name == "Fix What's Broken"

    def test_card_types(self) -> None:
        """Fix What's Broken must have correct card types."""
        card = FixWhatsBroken(name="Fix What's Broken", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Fix What's Broken must have converted mana cost 4."""
        card = FixWhatsBroken(name="Fix What's Broken", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Fix What's Broken must have correct colors."""
        card = FixWhatsBroken(name="Fix What's Broken", owner=None)
        assert "B" in card_colors(card)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestFixWhatsBrokenAbilities:
    """Ability tests for Fix What's Broken — expected to fail against stubs."""

    def test_additional_cost_declared(self) -> None:
        """Card must declare additional cost mechanism."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = FixWhatsBroken(name="Fix What's Broken", owner=player)
        card.controller = player
        has_addl = (
            hasattr(card, "additional_costs") or
            hasattr(card, "get_additional_costs") or
            (hasattr(card, "rules_text") and "additional cost" in (card.rules_text or "").lower())
        )
        assert has_addl, "Card must declare additional cost"

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = FixWhatsBroken(name="Fix What's Broken", owner=player)
        card.controller = player
        card._targets = [gy_card]
        if hasattr(card, "set_targets"):
            card.set_targets([gy_card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after < gy_before, (
            f"Should return from gy: {gy_before} -> {gy_after}"
        )

@pytest.mark.edge
class TestFixWhatsBrokenEdgeCases:
    """Edge case tests for Fix What's Broken."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = FixWhatsBroken(name="Fix What's Broken", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestFixWhatsBrokenInteractions:
    """Interaction tests for Fix What's Broken."""

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
        card = FixWhatsBroken(name="Fix What's Broken", owner=player)
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
        card = FixWhatsBroken(name="Fix What's Broken", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
