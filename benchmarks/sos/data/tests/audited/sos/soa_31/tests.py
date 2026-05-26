"""Audited tests for Locust Spray (collector key soa_31).

Verifies the Locust Spray card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import LocustSpray

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestLocustSprayBasicProperties:
    """Basic property tests for Locust Spray."""

    def test_is_instant(self) -> None:
        """Locust Spray must be a Instant subclass."""
        card = LocustSpray(name="Locust Spray", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """LocustSpray.name must be 'Locust Spray'."""
        card = LocustSpray(name="Locust Spray", owner=None)
        assert card.name == "Locust Spray"

    def test_card_types(self) -> None:
        """Locust Spray must have correct card types."""
        card = LocustSpray(name="Locust Spray", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Locust Spray must have converted mana cost 1."""
        card = LocustSpray(name="Locust Spray", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colors(self) -> None:
        """Locust Spray must have correct colors."""
        card = LocustSpray(name="Locust Spray", owner=None)
        assert "B" in card_colors(card)

@pytest.mark.ability
class TestLocustSprayAbilities:
    """Ability tests for Locust Spray — expected to fail against stubs."""

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
        card = LocustSpray(name="Locust Spray", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_causes_discard(self) -> None:
        """Resolution should cause discard."""
        from test_utils import create_game, set_board_state
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        filler = Sorcery(name="Discardable", owner=opponent)
        set_board_state(game, 1, hand=[filler])
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = LocustSpray(name="Locust Spray", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = LocustSpray(name="Locust Spray", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"

@pytest.mark.edge
class TestLocustSprayEdgeCases:
    """Edge case tests for Locust Spray."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = LocustSpray(name="Locust Spray", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True

@pytest.mark.interaction
class TestLocustSprayInteractions:
    """Interaction tests for Locust Spray."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = LocustSpray(name="Locust Spray", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = LocustSpray(name="Locust Spray", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
