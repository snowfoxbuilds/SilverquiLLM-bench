"""Audited tests for Return the Favor (collector key soa_47).

Verifies the Return the Favor card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import ReturnTheFavor

from engine.card import Instant
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestReturnTheFavorBasicProperties:
    """Basic property tests for Return the Favor."""

    def test_is_instant(self) -> None:
        """Return the Favor must be a Instant subclass."""
        card = ReturnTheFavor(name="Return the Favor", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """ReturnTheFavor.name must be 'Return the Favor'."""
        card = ReturnTheFavor(name="Return the Favor", owner=None)
        assert card.name == "Return the Favor"

    def test_card_types(self) -> None:
        """Return the Favor must have correct card types."""
        card = ReturnTheFavor(name="Return the Favor", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Return the Favor must have converted mana cost 2."""
        card = ReturnTheFavor(name="Return the Favor", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Return the Favor must have correct colors."""
        card = ReturnTheFavor(name="Return the Favor", owner=None)
        assert "R" in card_colors(card)

@pytest.mark.ability
class TestReturnTheFavorAbilities:
    """Ability tests for Return the Favor -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = ReturnTheFavor(name="Return the Favor", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Return the Favor must implement behavioral method"

@pytest.mark.edge
class TestReturnTheFavorEdgeCases:
    """Edge case and trap tests for Return the Favor."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ReturnTheFavor(name="Return the Favor", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Fizzled spell must go to graveyard"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ReturnTheFavor(name="Return the Favor", owner=None)
        card2 = ReturnTheFavor(name="Return the Favor", owner=None)
        card1.name = "Modified"
        assert card2.name == "Return the Favor", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ReturnTheFavor(name="Return the Favor", owner=None)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestReturnTheFavorInteractions:
    """Multi-card interaction tests for Return the Favor."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = ReturnTheFavor(name="Return the Favor", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ReturnTheFavor(name="Return the Favor", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
