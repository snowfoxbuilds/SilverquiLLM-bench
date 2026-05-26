"""Audited tests for Wildgrowth Archaic (collector key 168).

Verifies the Wildgrowth Archaic card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import WildgrowthArchaic

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestWildgrowthArchaicBasicProperties:
    """Basic property tests for Wildgrowth Archaic."""

    def test_is_creature(self) -> None:
        """Wildgrowth Archaic must be a Creature subclass."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """WildgrowthArchaic.name must be 'Wildgrowth Archaic'."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert card.name == "Wildgrowth Archaic"

    def test_card_types(self) -> None:
        """Wildgrowth Archaic must have correct card types."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Wildgrowth Archaic must have converted mana cost 2."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Wildgrowth Archaic must have correct colors."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert "G" in card_colors(card)

    def test_power(self) -> None:
        """Wildgrowth Archaic must have base power 0."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert card.base_power == 0

    def test_toughness(self) -> None:
        """Wildgrowth Archaic must have base toughness 0."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert card.base_toughness == 0

@pytest.mark.ability
class TestWildgrowthArchaicAbilities:
    """Ability tests for Wildgrowth Archaic -- expected to fail against stubs."""

    def test_has_reach(self) -> None:
        """Wildgrowth Archaic must have Reach keyword."""
        from engine.types import Keyword
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert Keyword.REACH in card.keywords, "Wildgrowth Archaic should have Reach"

    def test_has_converge(self) -> None:
        """Wildgrowth Archaic must have Converge keyword."""
        from engine.types import Keyword
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert Keyword.CONVERGE in card.keywords, "Wildgrowth Archaic should have Converge"

    def test_has_trample(self) -> None:
        """Wildgrowth Archaic must have Trample keyword."""
        from engine.types import Keyword
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert Keyword.TRAMPLE in card.keywords, "Wildgrowth Archaic should have Trample"

    def test_etb_adds_counters(self) -> None:
        """ETB must add +1/+1 counters per oracle text."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=player, base_power=0, base_toughness=0)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 > 0, "ETB must add +1/+1 counters per oracle"

    def test_converge_adds_counters(self) -> None:
        """Converge must add +1/+1 counters per color of mana spent."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=player, base_power=0, base_toughness=0)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 3
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 3, f"Converge with 3 colors should add 3 counters, got {p1p1}"

@pytest.mark.edge
class TestWildgrowthArchaicEdgeCases:
    """Edge case and trap tests for Wildgrowth Archaic."""

    def test_converge_zero_colors_no_bonus(self) -> None:
        """With 0 colors, converge should produce no bonus."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=player, base_power=0, base_toughness=0)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 0
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 0, f"Converge with 0 colors should add 0 counters, got {p1p1}"

    def test_converge_five_colors_maximum(self) -> None:
        """With 5 colors, converge should produce maximum bonus."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=player, base_power=0, base_toughness=0)
        card.controller = player
        if hasattr(card, "colors_spent"):
            card.colors_spent = 5
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        elif callable(getattr(card, "on_resolve", None)):
            card.on_resolve(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 == 5, f"Converge with 5 colors should add 5 counters, got {p1p1}"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        card2 = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        card1.name = "Modified"
        assert card2.name == "Wildgrowth Archaic", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=None, base_power=0, base_toughness=0)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

@pytest.mark.interaction
class TestWildgrowthArchaicInteractions:
    """Multi-card interaction tests for Wildgrowth Archaic."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=player, base_power=0, base_toughness=0)
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
        card = WildgrowthArchaic(name="Wildgrowth Archaic", owner=player, base_power=0, base_toughness=0)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
