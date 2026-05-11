"""Audited tests for Big Score (collector key soa_38).

Verifies the Big Score card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import BigScore

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBigScoreBasicProperties:
    """Basic property tests for Big Score."""

    def test_is_instant(self) -> None:
        """Big Score must be a Instant subclass."""
        card = BigScore(name="Big Score", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """BigScore.name must be 'Big Score'."""
        card = BigScore(name="Big Score", owner=None)
        assert card.name == "Big Score"

    def test_card_types(self) -> None:
        """Big Score must have correct card types."""
        card = BigScore(name="Big Score", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Big Score must have converted mana cost 4."""
        card = BigScore(name="Big Score", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Big Score must have correct colors."""
        card = BigScore(name="Big Score", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestBigScoreAbilities:
    """Ability tests for Big Score — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BigScore(name="Big Score", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = BigScore(name="Big Score", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_causes_discard(self) -> None:
        """Resolution should cause discard."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        filler = Sorcery(name="Discardable", owner=opponent)
        set_board_state(game, 1, hand=[filler])
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = BigScore(name="Big Score", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_additional_cost_declared(self) -> None:
        """Card must declare additional cost mechanism."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BigScore(name="Big Score", owner=player)
        card.controller = player
        has_addl = (
            hasattr(card, "additional_costs") or
            hasattr(card, "get_additional_costs") or
            (hasattr(card, "rules_text") and "additional cost" in (card.rules_text or "").lower())
        )
        assert has_addl, "Card must declare additional cost"

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = BigScore(name="Big Score", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestBigScoreEdgeCases:
    """Edge case tests for Big Score."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BigScore(name="Big Score", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestBigScoreInteractions:
    """Interaction tests for Big Score."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = BigScore(name="Big Score", owner=player)
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
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = BigScore(name="Big Score", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
