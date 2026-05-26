"""Audited tests for Wisdom of Ages (collector key 71).

Verifies the Wisdom of Ages card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import WisdomOfAges

from engine.card import Sorcery
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestWisdomOfAgesBasicProperties:
    """Basic property tests for Wisdom of Ages."""

    def test_is_sorcery(self) -> None:
        """Wisdom of Ages must be a Sorcery subclass."""
        card = WisdomOfAges(name="Wisdom of Ages", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """WisdomOfAges.name must be 'Wisdom of Ages'."""
        card = WisdomOfAges(name="Wisdom of Ages", owner=None)
        assert card.name == "Wisdom of Ages"

    def test_card_types(self) -> None:
        """Wisdom of Ages must have correct card types."""
        card = WisdomOfAges(name="Wisdom of Ages", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Wisdom of Ages must have converted mana cost 7."""
        card = WisdomOfAges(name="Wisdom of Ages", owner=None)
        assert card.mana_cost.cmc == 7

    def test_colors(self) -> None:
        """Wisdom of Ages must have correct colors."""
        card = WisdomOfAges(name="Wisdom of Ages", owner=None)
        assert "U" in card_colors(card)

@pytest.mark.ability
class TestWisdomOfAgesAbilities:
    """Ability tests for Wisdom of Ages — expected to fail against stubs."""

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = WisdomOfAges(name="Wisdom of Ages", owner=player)
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
class TestWisdomOfAgesEdgeCases:
    """Edge case tests for Wisdom of Ages."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = WisdomOfAges(name="Wisdom of Ages", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestWisdomOfAgesInteractions:
    """Interaction tests for Wisdom of Ages."""

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
        card = WisdomOfAges(name="Wisdom of Ages", owner=player)
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
        card = WisdomOfAges(name="Wisdom of Ages", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
