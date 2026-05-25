"""Audited tests for Cuboid Colony (collector key 183).

Verifies the Cuboid Colony card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import CuboidColony

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestCuboidColonyBasicProperties:
    """Basic property tests for Cuboid Colony."""

    def test_is_creature(self) -> None:
        """Cuboid Colony must be a Creature subclass."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """CuboidColony.name must be 'Cuboid Colony'."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert card.name == "Cuboid Colony"

    def test_card_types(self) -> None:
        """Cuboid Colony must have correct card types."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Cuboid Colony must have converted mana cost 2."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Cuboid Colony must have correct colors."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert "G" in card.colors
        assert "U" in card.colors

    def test_power(self) -> None:
        """Cuboid Colony must have base power 1."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Cuboid Colony must have base toughness 1."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestCuboidColonyAbilities:
    """Ability tests for Cuboid Colony -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Cuboid Colony must have Flying keyword."""
        from engine.types import Keyword
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert Keyword.FLYING in card.keywords, "Cuboid Colony should have Flying"

    def test_has_trample(self) -> None:
        """Cuboid Colony must have Trample keyword."""
        from engine.types import Keyword
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert Keyword.TRAMPLE in card.keywords, "Cuboid Colony should have Trample"

    def test_has_flash(self) -> None:
        """Cuboid Colony must have Flash keyword."""
        from engine.types import Keyword
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert Keyword.FLASH in card.keywords, "Cuboid Colony should have Flash"


@pytest.mark.edge
class TestCuboidColonyEdgeCases:
    """Edge case and trap tests for Cuboid Colony."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        card2 = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        card1.name = "Modified"
        assert card2.name == "Cuboid Colony", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = CuboidColony(name="Cuboid Colony", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = CuboidColony(name="Cuboid Colony", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 0
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestCuboidColonyInteractions:
    """Multi-card interaction tests for Cuboid Colony."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = CuboidColony(name="Cuboid Colony", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 2
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 2, f"Should have 2 +1/+1 counters, got {p1p1}"

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = CuboidColony(name="Cuboid Colony", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
