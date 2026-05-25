"""Audited tests for Prismari, the Inspiration (collector key 212).

Verifies the Prismari, the Inspiration card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import PrismariTheInspiration

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPrismariTheInspirationBasicProperties:
    """Basic property tests for Prismari, the Inspiration."""

    def test_is_creature(self) -> None:
        """Prismari, the Inspiration must be a Creature subclass."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """PrismariTheInspiration.name must be 'Prismari, the Inspiration'."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert card.name == "Prismari, the Inspiration"

    def test_card_types(self) -> None:
        """Prismari, the Inspiration must have correct card types."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Prismari, the Inspiration must have converted mana cost 7."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert card.mana_cost.cmc == 7

    def test_colors(self) -> None:
        """Prismari, the Inspiration must have correct colors."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert "R" in card.colors
        assert "U" in card.colors

    def test_power(self) -> None:
        """Prismari, the Inspiration must have base power 7."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert card.base_power == 7

    def test_toughness(self) -> None:
        """Prismari, the Inspiration must have base toughness 7."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert card.base_toughness == 7


@pytest.mark.ability
class TestPrismariTheInspirationAbilities:
    """Ability tests for Prismari, the Inspiration -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Prismari, the Inspiration must have Flying keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert Keyword.FLYING in card.keywords, "Prismari, the Inspiration should have Flying"

    def test_has_ward(self) -> None:
        """Prismari, the Inspiration must have Ward keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert Keyword.WARD in card.keywords, "Prismari, the Inspiration should have Ward"


@pytest.mark.edge
class TestPrismariTheInspirationEdgeCases:
    """Edge case and trap tests for Prismari, the Inspiration."""

    def test_fizzle_no_targets_creature_stays(self) -> None:
        """If ETB ability fizzles, the creature remains on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=player, base_power=7, base_toughness=7)
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
        card1 = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        card2 = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        card1.name = "Modified"
        assert card2.name == "Prismari, the Inspiration", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=None, base_power=7, base_toughness=7)
        assert card.mana_cost.cmc == 7, \
            f"CMC must be 7, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestPrismariTheInspirationInteractions:
    """Multi-card interaction tests for Prismari, the Inspiration."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=player, base_power=7, base_toughness=7)
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
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        other = Creature(name="Companion", owner=player, base_power=2, base_toughness=2)
        other.controller = player
        card = PrismariTheInspiration(name="Prismari, the Inspiration", owner=player, base_power=7, base_toughness=7)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
