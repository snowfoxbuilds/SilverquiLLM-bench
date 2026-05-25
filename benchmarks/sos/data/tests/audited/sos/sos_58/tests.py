"""Audited tests for Mathemagics (collector key 58).

Verifies the Mathemagics card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Mathemagics

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMathemagicsBasicProperties:
    """Basic property tests for Mathemagics."""

    def test_is_sorcery(self) -> None:
        """Mathemagics must be a Sorcery subclass."""
        card = Mathemagics(name="Mathemagics", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """Mathemagics.name must be 'Mathemagics'."""
        card = Mathemagics(name="Mathemagics", owner=None)
        assert card.name == "Mathemagics"

    def test_card_types(self) -> None:
        """Mathemagics must have correct card types."""
        card = Mathemagics(name="Mathemagics", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Mathemagics must have converted mana cost 2."""
        card = Mathemagics(name="Mathemagics", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Mathemagics must have correct colors."""
        card = Mathemagics(name="Mathemagics", owner=None)
        assert "U" in card.colors


@pytest.mark.ability
class TestMathemagicsAbilities:
    """Ability tests for Mathemagics — expected to fail against stubs."""

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
        card = Mathemagics(name="Mathemagics", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )


@pytest.mark.edge
class TestMathemagicsEdgeCases:
    """Edge case tests for Mathemagics."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Mathemagics(name="Mathemagics", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestMathemagicsInteractions:
    """Interaction tests for Mathemagics."""

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
        card = Mathemagics(name="Mathemagics", owner=player)
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
        card = Mathemagics(name="Mathemagics", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
