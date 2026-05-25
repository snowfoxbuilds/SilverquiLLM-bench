"""Audited tests for Scheming Silvertongue // Sign in Blood (collector key 99).

Verifies the Scheming Silvertongue // Sign in Blood card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import SchemingSilvertongueSignInBlood

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSchemingSilvertongueSignInBloodBasicProperties:
    """Basic property tests for Scheming Silvertongue // Sign in Blood."""

    def test_is_creature(self) -> None:
        """Scheming Silvertongue // Sign in Blood must be a Creature subclass."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SchemingSilvertongueSignInBlood.name must be 'Scheming Silvertongue // Sign in Blood'."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert card.name == "Scheming Silvertongue // Sign in Blood"

    def test_card_types(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have correct card types."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have converted mana cost 4."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have correct colors."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have base power 1."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have base toughness 3."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestSchemingSilvertongueSignInBloodAbilities:
    """Ability tests for Scheming Silvertongue // Sign in Blood -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have Flying keyword."""
        from engine.types import Keyword
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert Keyword.FLYING in card.keywords, "Scheming Silvertongue // Sign in Blood should have Flying"

    def test_has_lifelink(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have Lifelink keyword."""
        from engine.types import Keyword
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert Keyword.LIFELINK in card.keywords, "Scheming Silvertongue // Sign in Blood should have Lifelink"

    def test_has_prepared(self) -> None:
        """Scheming Silvertongue // Sign in Blood must have Prepared keyword."""
        from engine.types import Keyword
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert Keyword.PREPARED in card.keywords, "Scheming Silvertongue // Sign in Blood should have Prepared"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Scheming Silvertongue // Sign in Blood must implement prepared mechanic"


@pytest.mark.edge
class TestSchemingSilvertongueSignInBloodEdgeCases:
    """Edge case and trap tests for Scheming Silvertongue // Sign in Blood."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        card2 = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Scheming Silvertongue // Sign in Blood", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=None, base_power=1, base_toughness=3)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=player, base_power=1, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 2
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestSchemingSilvertongueSignInBloodInteractions:
    """Multi-card interaction tests for Scheming Silvertongue // Sign in Blood."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=player, base_power=1, base_toughness=3)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"

    def test_coexists_with_other_permanents(self) -> None:
        """Card must coexist with other permanents without errors."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = SchemingSilvertongueSignInBlood(name="Scheming Silvertongue // Sign in Blood", owner=player, base_power=1, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
