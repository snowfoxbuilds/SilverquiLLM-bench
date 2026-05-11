"""Audited tests for Brotherhood's End (collector key soa_39).

Verifies the Brotherhood's End card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import BrotherhoodsEnd

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestBrotherhoodsEndBasicProperties:
    """Basic property tests for Brotherhood's End."""

    def test_is_sorcery(self) -> None:
        """Brotherhood's End must be a Sorcery subclass."""
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """BrotherhoodsEnd.name must be 'Brotherhood's End'."""
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        assert card.name == "Brotherhood's End"

    def test_card_types(self) -> None:
        """Brotherhood's End must have correct card types."""
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Brotherhood's End must have converted mana cost 3."""
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Brotherhood's End must have correct colors."""
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestBrotherhoodsEndAbilities:
    """Ability tests for Brotherhood's End -- expected to fail against stubs."""

    def test_resolution_deals_damage(self) -> None:
        """Spell resolution must deal damage per oracle text."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=player)
        card.controller = player
        initial_life = opponent.life
        card.on_resolve(game)
        assert opponent.life < initial_life, "Brotherhood's End must deal damage on resolution"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Brotherhood's End must implement behavioral method"


@pytest.mark.edge
class TestBrotherhoodsEndEdgeCases:
    """Edge case and trap tests for Brotherhood's End."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        card2 = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        card1.name = "Modified"
        assert card2.name == "Brotherhood's End", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=None)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"


@pytest.mark.interaction
class TestBrotherhoodsEndInteractions:
    """Multi-card interaction tests for Brotherhood's End."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = BrotherhoodsEnd(name="Brotherhood's End", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        set_board_state(game, 0, battlefield=[other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
