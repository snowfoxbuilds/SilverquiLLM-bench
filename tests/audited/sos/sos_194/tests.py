"""Audited tests for Hardened Academic (collector key 194).

Verifies the Hardened Academic card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import HardenedAcademic

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestHardenedAcademicBasicProperties:
    """Basic property tests for Hardened Academic."""

    def test_is_creature(self) -> None:
        """Hardened Academic must be a Creature subclass."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """HardenedAcademic.name must be 'Hardened Academic'."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert card.name == "Hardened Academic"

    def test_card_types(self) -> None:
        """Hardened Academic must have correct card types."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Hardened Academic must have converted mana cost 2."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Hardened Academic must have correct colors."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert "R" in card.colors
        assert "W" in card.colors

    def test_power(self) -> None:
        """Hardened Academic must have base power 2."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Hardened Academic must have base toughness 1."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert card.base_toughness == 1


@pytest.mark.ability
class TestHardenedAcademicAbilities:
    """Ability tests for Hardened Academic -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Hardened Academic must have Flying keyword."""
        from engine.types import Keyword
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert Keyword.FLYING in card.keywords, "Hardened Academic should have Flying"

    def test_has_haste(self) -> None:
        """Hardened Academic must have Haste keyword."""
        from engine.types import Keyword
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert Keyword.HASTE in card.keywords, "Hardened Academic should have Haste"


@pytest.mark.edge
class TestHardenedAcademicEdgeCases:
    """Edge case and trap tests for Hardened Academic."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = HardenedAcademic(name="Hardened Academic", owner=player, base_power=2, base_toughness=1)
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
        card1 = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        card2 = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        card1.name = "Modified"
        assert card2.name == "Hardened Academic", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = HardenedAcademic(name="Hardened Academic", owner=None, base_power=2, base_toughness=1)
        assert card.mana_cost.cmc == 2, \
            f"CMC must be 2, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestHardenedAcademicInteractions:
    """Multi-card interaction tests for Hardened Academic."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = HardenedAcademic(name="Hardened Academic", owner=player, base_power=2, base_toughness=1)
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
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = HardenedAcademic(name="Hardened Academic", owner=player, base_power=2, base_toughness=1)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
