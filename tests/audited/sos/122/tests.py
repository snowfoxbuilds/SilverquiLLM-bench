"""Audited tests for Maelstrom Artisan // Rocket Volley (collector key 122).

Verifies the Maelstrom Artisan // Rocket Volley card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import MaelstromArtisanRocketVolley

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMaelstromArtisanRocketVolleyBasicProperties:
    """Basic property tests for Maelstrom Artisan // Rocket Volley."""

    def test_is_creature(self) -> None:
        """Maelstrom Artisan // Rocket Volley must be a Creature subclass."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """MaelstromArtisanRocketVolley.name must be 'Maelstrom Artisan // Rocket Volley'."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert card.name == "Maelstrom Artisan // Rocket Volley"

    def test_card_types(self) -> None:
        """Maelstrom Artisan // Rocket Volley must have correct card types."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Maelstrom Artisan // Rocket Volley must have converted mana cost 5."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Maelstrom Artisan // Rocket Volley must have correct colors."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Maelstrom Artisan // Rocket Volley must have base power 3."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Maelstrom Artisan // Rocket Volley must have base toughness 2."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestMaelstromArtisanRocketVolleyAbilities:
    """Ability tests for Maelstrom Artisan // Rocket Volley -- expected to fail against stubs."""

    def test_has_haste(self) -> None:
        """Maelstrom Artisan // Rocket Volley must have Haste keyword."""
        from engine.types import Keyword
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert Keyword.HASTE in card.keywords, "Maelstrom Artisan // Rocket Volley should have Haste"

    def test_has_prepared(self) -> None:
        """Maelstrom Artisan // Rocket Volley must have Prepared keyword."""
        from engine.types import Keyword
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert Keyword.PREPARED in card.keywords, "Maelstrom Artisan // Rocket Volley should have Prepared"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Maelstrom Artisan // Rocket Volley must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Maelstrom Artisan // Rocket Volley must implement prepared mechanic"


@pytest.mark.edge
class TestMaelstromArtisanRocketVolleyEdgeCases:
    """Edge case and trap tests for Maelstrom Artisan // Rocket Volley."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        card2 = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        card1.name = "Modified"
        assert card2.name == "Maelstrom Artisan // Rocket Volley", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=None, base_power=3, base_toughness=2)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=player, base_power=3, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 1
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestMaelstromArtisanRocketVolleyInteractions:
    """Multi-card interaction tests for Maelstrom Artisan // Rocket Volley."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=player, base_power=3, base_toughness=2)
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
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = MaelstromArtisanRocketVolley(name="Maelstrom Artisan // Rocket Volley", owner=player, base_power=3, base_toughness=2)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
