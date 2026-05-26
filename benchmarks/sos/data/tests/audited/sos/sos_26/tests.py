"""Audited tests for Primary Research (collector key 26).

Verifies the Primary Research card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import PrimaryResearch

from engine.card import Enchantment
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestPrimaryResearchBasicProperties:
    """Basic property tests for Primary Research."""

    def test_is_enchantment(self) -> None:
        """Primary Research must be a Enchantment subclass."""
        card = PrimaryResearch(name="Primary Research", owner=None)
        assert isinstance(card, Enchantment)

    def test_name(self) -> None:
        """PrimaryResearch.name must be 'Primary Research'."""
        card = PrimaryResearch(name="Primary Research", owner=None)
        assert card.name == "Primary Research"

    def test_card_types(self) -> None:
        """Primary Research must have correct card types."""
        card = PrimaryResearch(name="Primary Research", owner=None)
        assert CardType.ENCHANTMENT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Primary Research must have converted mana cost 5."""
        card = PrimaryResearch(name="Primary Research", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Primary Research must have correct colors."""
        card = PrimaryResearch(name="Primary Research", owner=None)
        assert "W" in card_colors(card)

@pytest.mark.ability
class TestPrimaryResearchAbilities:
    """Ability tests for Primary Research — expected to fail against stubs."""

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = PrimaryResearch(name="Primary Research", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = PrimaryResearch(name="Primary Research", owner=player)
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
class TestPrimaryResearchEdgeCases:
    """Edge case tests for Primary Research."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PrimaryResearch(name="Primary Research", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestPrimaryResearchInteractions:
    """Interaction tests for Primary Research."""

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
        card = PrimaryResearch(name="Primary Research", owner=player)
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
        card = PrimaryResearch(name="Primary Research", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
