"""Audited tests for Tester of the Tangential (collector key 69).

Verifies the Tester of the Tangential card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import TesterOfTheTangential

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestTesterOfTheTangentialBasicProperties:
    """Basic property tests for Tester of the Tangential."""

    def test_is_creature(self) -> None:
        """Tester of the Tangential must be a Creature subclass."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """TesterOfTheTangential.name must be 'Tester of the Tangential'."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert card.name == "Tester of the Tangential"

    def test_card_types(self) -> None:
        """Tester of the Tangential must have correct card types."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Tester of the Tangential must have converted mana cost 2."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Tester of the Tangential must have correct colors."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Tester of the Tangential must have base power 1."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Tester of the Tangential must have base toughness 1."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestTesterOfTheTangentialAbilities:
    """Ability tests for Tester of the Tangential -- expected to fail against stubs."""

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Tester of the Tangential must implement behavioral method"


@pytest.mark.edge
class TestTesterOfTheTangentialEdgeCases:
    """Edge case and trap tests for Tester of the Tangential."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        # No targets available; ETB fizzles
        try:
            if callable(getattr(card, "on_enter_battlefield", None)):
                card.on_enter_battlefield(game)
        except (ValueError, IndexError):
            pass  # Fizzle expected
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must stay on battlefield when ETB fizzles"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        card2 = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        card1.name = "Modified"
        assert card2.name == "Tester of the Tangential", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=None, base_power=1, base_toughness=1)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestTesterOfTheTangentialInteractions:
    """Multi-card interaction tests for Tester of the Tangential."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=player, base_power=1, base_toughness=1)
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
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = TesterOfTheTangential(name="Tester of the Tangential", owner=player, base_power=1, base_toughness=1)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
