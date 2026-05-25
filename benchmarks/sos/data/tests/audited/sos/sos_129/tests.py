"""Audited tests for Seize the Spoils (collector key 129).

Verifies the Seize the Spoils card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SeizeTheSpoils

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSeizeTheSpoilsBasicProperties:
    """Basic property tests for Seize the Spoils."""

    def test_is_sorcery(self) -> None:
        """Seize the Spoils must be a Sorcery subclass."""
        card = SeizeTheSpoils(name="Seize the Spoils", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """SeizeTheSpoils.name must be 'Seize the Spoils'."""
        card = SeizeTheSpoils(name="Seize the Spoils", owner=None)
        assert card.name == "Seize the Spoils"

    def test_card_types(self) -> None:
        """Seize the Spoils must have correct card types."""
        card = SeizeTheSpoils(name="Seize the Spoils", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Seize the Spoils must have converted mana cost 3."""
        card = SeizeTheSpoils(name="Seize the Spoils", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Seize the Spoils must have correct colors."""
        card = SeizeTheSpoils(name="Seize the Spoils", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestSeizeTheSpoilsAbilities:
    """Ability tests for Seize the Spoils — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

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
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
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
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_additional_cost_declared(self) -> None:
        """Card must declare additional cost mechanism."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
        card.controller = player
        has_addl = (
            hasattr(card, "additional_costs") or
            hasattr(card, "get_additional_costs") or
            (hasattr(card, "rules_text") and "additional cost" in (card.rules_text or "").lower())
        )
        assert has_addl, "Card must declare additional cost"

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestSeizeTheSpoilsEdgeCases:
    """Edge case tests for Seize the Spoils."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestSeizeTheSpoilsInteractions:
    """Interaction tests for Seize the Spoils."""

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
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
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
        card = SeizeTheSpoils(name="Seize the Spoils", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
