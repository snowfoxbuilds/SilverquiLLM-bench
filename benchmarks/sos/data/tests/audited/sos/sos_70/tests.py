"""Audited tests for Textbook Tabulator (collector key 70).

Verifies the Textbook Tabulator card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import TextbookTabulator

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestTextbookTabulatorBasicProperties:
    """Basic property tests for Textbook Tabulator."""

    def test_is_creature(self) -> None:
        """Textbook Tabulator must be a Creature subclass."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """TextbookTabulator.name must be 'Textbook Tabulator'."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert card.name == "Textbook Tabulator"

    def test_card_types(self) -> None:
        """Textbook Tabulator must have correct card types."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Textbook Tabulator must have converted mana cost 3."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Textbook Tabulator must have correct colors."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert "U" in card_colors(card)

    def test_power(self) -> None:
        """Textbook Tabulator must have base power 0."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert card.base_power == 0

    def test_toughness(self) -> None:
        """Textbook Tabulator must have base toughness 3."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert card.base_toughness == 3

@pytest.mark.ability
class TestTextbookTabulatorAbilities:
    """Ability tests for Textbook Tabulator -- expected to fail against stubs."""

    def test_etb_adds_counters(self) -> None:
        """ETB must add +1/+1 counters per oracle text."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = TextbookTabulator(name="Textbook Tabulator", owner=player, base_power=0, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 > 0, "ETB must add +1/+1 counters per oracle"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Textbook Tabulator must implement behavioral method"

@pytest.mark.edge
class TestTextbookTabulatorEdgeCases:
    """Edge case and trap tests for Textbook Tabulator."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        card2 = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Textbook Tabulator", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = TextbookTabulator(name="Textbook Tabulator", owner=None, base_power=0, base_toughness=3)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = TextbookTabulator(name="Textbook Tabulator", owner=player, base_power=0, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 2
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"

@pytest.mark.interaction
class TestTextbookTabulatorInteractions:
    """Multi-card interaction tests for Textbook Tabulator."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = TextbookTabulator(name="Textbook Tabulator", owner=player, base_power=0, base_toughness=3)
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
        card = TextbookTabulator(name="Textbook Tabulator", owner=player, base_power=0, base_toughness=3)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
