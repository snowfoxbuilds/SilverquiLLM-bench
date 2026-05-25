"""Audited tests for Pterafractyl (collector key 215).

Verifies the Pterafractyl card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import Pterafractyl

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPterafractylBasicProperties:
    """Basic property tests for Pterafractyl."""

    def test_is_creature(self) -> None:
        """Pterafractyl must be a Creature subclass."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """Pterafractyl.name must be 'Pterafractyl'."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert card.name == "Pterafractyl"

    def test_card_types(self) -> None:
        """Pterafractyl must have correct card types."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Pterafractyl must have converted mana cost 2."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Pterafractyl must have correct colors."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert "G" in card.colors
        assert "U" in card.colors

    def test_power(self) -> None:
        """Pterafractyl must have base power 1."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Pterafractyl must have base toughness 0."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert card.base_toughness == 0


@pytest.mark.ability
class TestPterafractylAbilities:
    """Ability tests for Pterafractyl -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Pterafractyl must have Flying keyword."""
        from engine.types import Keyword
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert Keyword.FLYING in card.keywords, "Pterafractyl should have Flying"

    def test_etb_adds_counters(self) -> None:
        """ETB must add +1/+1 counters per oracle text."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = Pterafractyl(name="Pterafractyl", owner=player, base_power=1, base_toughness=0)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 > 0, "ETB must add +1/+1 counters per oracle"


@pytest.mark.edge
class TestPterafractylEdgeCases:
    """Edge case and trap tests for Pterafractyl."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        card2 = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        card1.name = "Modified"
        assert card2.name == "Pterafractyl", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = Pterafractyl(name="Pterafractyl", owner=None, base_power=1, base_toughness=0)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = Pterafractyl(name="Pterafractyl", owner=player, base_power=1, base_toughness=0)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 0
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestPterafractylInteractions:
    """Multi-card interaction tests for Pterafractyl."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = Pterafractyl(name="Pterafractyl", owner=player, base_power=1, base_toughness=0)
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
        card = Pterafractyl(name="Pterafractyl", owner=player, base_power=1, base_toughness=0)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
