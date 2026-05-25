"""Audited tests for Social Snub (collector key 228).

Verifies the Social Snub card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SocialSnub

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSocialSnubBasicProperties:
    """Basic property tests for Social Snub."""

    def test_is_sorcery(self) -> None:
        """Social Snub must be a Sorcery subclass."""
        card = SocialSnub(name="Social Snub", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """SocialSnub.name must be 'Social Snub'."""
        card = SocialSnub(name="Social Snub", owner=None)
        assert card.name == "Social Snub"

    def test_card_types(self) -> None:
        """Social Snub must have correct card types."""
        card = SocialSnub(name="Social Snub", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Social Snub must have converted mana cost 3."""
        card = SocialSnub(name="Social Snub", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Social Snub must have correct colors."""
        card = SocialSnub(name="Social Snub", owner=None)
        assert "B" in card.colors
        assert "W" in card.colors


@pytest.mark.ability
class TestSocialSnubAbilities:
    """Ability tests for Social Snub — expected to fail against stubs."""

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SocialSnub(name="Social Snub", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

    def test_causes_life_loss(self) -> None:
        """Resolution should cause life loss."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = SocialSnub(name="Social Snub", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )


@pytest.mark.edge
class TestSocialSnubEdgeCases:
    """Edge case tests for Social Snub."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SocialSnub(name="Social Snub", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestSocialSnubInteractions:
    """Interaction tests for Social Snub."""

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
        card = SocialSnub(name="Social Snub", owner=player)
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
        card = SocialSnub(name="Social Snub", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
