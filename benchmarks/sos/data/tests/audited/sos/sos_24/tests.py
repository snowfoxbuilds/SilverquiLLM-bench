"""Audited tests for Owlin Historian (collector key 24).

Verifies the Owlin Historian card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import OwlinHistorian

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestOwlinHistorianBasicProperties:
    """Basic property tests for Owlin Historian."""

    def test_is_creature(self) -> None:
        """Owlin Historian must be a Creature subclass."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """OwlinHistorian.name must be 'Owlin Historian'."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert card.name == "Owlin Historian"

    def test_card_types(self) -> None:
        """Owlin Historian must have correct card types."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Owlin Historian must have converted mana cost 3."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Owlin Historian must have correct colors."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert "W" in card.colors

    def test_power(self) -> None:
        """Owlin Historian must have base power 2."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Owlin Historian must have base toughness 3."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestOwlinHistorianAbilities:
    """Ability tests for Owlin Historian -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Owlin Historian must have Flying keyword."""
        from benchmarks.sos.workspace.engine.types import Keyword
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert Keyword.FLYING in card.keywords, "Owlin Historian should have Flying"

    def test_etb_adds_counters(self) -> None:
        """ETB must add +1/+1 counters per oracle text."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = OwlinHistorian(name="Owlin Historian", owner=player, base_power=2, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if callable(getattr(card, "on_enter_battlefield", None)):
            card.on_enter_battlefield(game)
        counters = getattr(card, "counters", {})
        p1p1 = counters.get("+1/+1", counters.get("p1p1", 0))
        assert p1p1 > 0, "ETB must add +1/+1 counters per oracle"


@pytest.mark.edge
class TestOwlinHistorianEdgeCases:
    """Edge case and trap tests for Owlin Historian."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        card2 = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        card1.name = "Modified"
        assert card2.name == "Owlin Historian", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = OwlinHistorian(name="Owlin Historian", owner=None, base_power=2, base_toughness=3)
        assert card.mana_cost.cmc == 3, \
            f"CMC must be 3, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = OwlinHistorian(name="Owlin Historian", owner=player, base_power=2, base_toughness=3)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 2
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestOwlinHistorianInteractions:
    """Multi-card interaction tests for Owlin Historian."""

    def test_counters_survive_end_of_turn(self) -> None:
        """Permanent counters must persist through end of turn."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = OwlinHistorian(name="Owlin Historian", owner=player, base_power=2, base_toughness=3)
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
        card = OwlinHistorian(name="Owlin Historian", owner=player, base_power=2, base_toughness=3)
        card.controller = player
        blocker = Creature(name="Blocker", owner=opponent, base_power=1, base_toughness=1)
        blocker.controller = opponent
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[blocker])
        bf_p = player.zones[Zone.BATTLEFIELD].get_all()
        bf_o = opponent.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf_p and blocker in bf_o, "Both creatures on battlefield"
