"""Audited tests for Resonating Lute (collector key 221).

Verifies the Resonating Lute card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ResonatingLute

from engine.card import Artifact
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestResonatingLuteBasicProperties:
    """Basic property tests for Resonating Lute."""

    def test_is_artifact(self) -> None:
        """Resonating Lute must be a Artifact subclass."""
        card = ResonatingLute(name="Resonating Lute", owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        """ResonatingLute.name must be 'Resonating Lute'."""
        card = ResonatingLute(name="Resonating Lute", owner=None)
        assert card.name == "Resonating Lute"

    def test_card_types(self) -> None:
        """Resonating Lute must have correct card types."""
        card = ResonatingLute(name="Resonating Lute", owner=None)
        assert CardType.ARTIFACT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Resonating Lute must have converted mana cost 4."""
        card = ResonatingLute(name="Resonating Lute", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Resonating Lute must have correct colors."""
        card = ResonatingLute(name="Resonating Lute", owner=None)
        assert "R" in card.colors
        assert "U" in card.colors


@pytest.mark.ability
class TestResonatingLuteAbilities:
    """Ability tests for Resonating Lute — expected to fail against stubs."""

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
        card = ResonatingLute(name="Resonating Lute", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ResonatingLute(name="Resonating Lute", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestResonatingLuteEdgeCases:
    """Edge case tests for Resonating Lute."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ResonatingLute(name="Resonating Lute", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestResonatingLuteInteractions:
    """Interaction tests for Resonating Lute."""

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
        card = ResonatingLute(name="Resonating Lute", owner=player)
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
        card = ResonatingLute(name="Resonating Lute", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
