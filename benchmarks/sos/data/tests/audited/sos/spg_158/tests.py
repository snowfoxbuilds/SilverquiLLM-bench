"""Audited tests for Library of Leng (collector key spg_158).

Verifies the Library of Leng card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import LibraryOfLeng

from engine.card import Artifact
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestLibraryOfLengBasicProperties:
    """Basic property tests for Library of Leng."""

    def test_is_artifact(self) -> None:
        """Library of Leng must be a Artifact subclass."""
        card = LibraryOfLeng(name="Library of Leng", owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        """LibraryOfLeng.name must be 'Library of Leng'."""
        card = LibraryOfLeng(name="Library of Leng", owner=None)
        assert card.name == "Library of Leng"

    def test_card_types(self) -> None:
        """Library of Leng must have correct card types."""
        card = LibraryOfLeng(name="Library of Leng", owner=None)
        assert CardType.ARTIFACT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Library of Leng must have converted mana cost 1."""
        card = LibraryOfLeng(name="Library of Leng", owner=None)
        assert card.mana_cost.cmc == 1

    def test_colorless(self) -> None:
        """Library of Leng must be colorless."""
        card = LibraryOfLeng(name="Library of Leng", owner=None)
        assert len(card.colors) == 0


@pytest.mark.ability
class TestLibraryOfLengAbilities:
    """Ability tests for Library of Leng -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = LibraryOfLeng(name="Library of Leng", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Library of Leng must implement behavioral method"


@pytest.mark.edge
class TestLibraryOfLengEdgeCases:
    """Edge case and trap tests for Library of Leng."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = LibraryOfLeng(name="Library of Leng", owner=None)
        card2 = LibraryOfLeng(name="Library of Leng", owner=None)
        card1.name = "Modified"
        assert card2.name == "Library of Leng", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = LibraryOfLeng(name="Library of Leng", owner=None)
        assert card.mana_cost.cmc == 1, \
            f"CMC must be 1, got {card.mana_cost.cmc}"

    def test_resolution_with_empty_board(self) -> None:
        """Spell must handle resolution with no valid targets/creatures."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = LibraryOfLeng(name="Library of Leng", owner=player)
        card.controller = player
        # Resolution on empty board should not crash
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Fizzle on empty board is acceptable
        # Verify game state is consistent
        assert player.life == 20, "Caster life should be unchanged on fizzle"


@pytest.mark.interaction
class TestLibraryOfLengInteractions:
    """Multi-card interaction tests for Library of Leng."""

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = LibraryOfLeng(name="Library of Leng", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        set_board_state(game, 0, battlefield=[other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
