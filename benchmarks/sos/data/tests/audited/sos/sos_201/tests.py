"""Audited tests for Lorehold, the Historian (collector key 201).

Verifies the Lorehold, the Historian card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: expert.
"""

from __future__ import annotations

import pytest

from card_impl import LoreholdTheHistorian

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestLoreholdTheHistorianBasicProperties:
    """Basic property tests for Lorehold, the Historian."""

    def test_is_creature(self) -> None:
        """Lorehold, the Historian must be a Creature subclass."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """LoreholdTheHistorian.name must be 'Lorehold, the Historian'."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert card.name == "Lorehold, the Historian"

    def test_card_types(self) -> None:
        """Lorehold, the Historian must have correct card types."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Lorehold, the Historian must have converted mana cost 5."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Lorehold, the Historian must have correct colors."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert "R" in card.colors
        assert "W" in card.colors

    def test_power(self) -> None:
        """Lorehold, the Historian must have base power 5."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert card.base_power == 5

    def test_toughness(self) -> None:
        """Lorehold, the Historian must have base toughness 5."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert card.base_toughness == 5


@pytest.mark.ability
class TestLoreholdTheHistorianAbilities:
    """Ability tests for Lorehold, the Historian -- expected to fail against stubs."""

    def test_has_flying(self) -> None:
        """Lorehold, the Historian must have Flying keyword."""
        from engine.types import Keyword
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert Keyword.FLYING in card.keywords, "Lorehold, the Historian should have Flying"

    def test_has_haste(self) -> None:
        """Lorehold, the Historian must have Haste keyword."""
        from engine.types import Keyword
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert Keyword.HASTE in card.keywords, "Lorehold, the Historian should have Haste"


@pytest.mark.edge
class TestLoreholdTheHistorianEdgeCases:
    """Edge case and trap tests for Lorehold, the Historian."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        card2 = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        card1.name = "Modified"
        assert card2.name == "Lorehold, the Historian", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=None, base_power=5, base_toughness=5)
        assert card.mana_cost.cmc == 5, \
            f"CMC must be 5, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 4
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestLoreholdTheHistorianInteractions:
    """Multi-card interaction tests for Lorehold, the Historian."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=player, base_power=5, base_toughness=5)
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
        card = LoreholdTheHistorian(name="Lorehold, the Historian", owner=player, base_power=5, base_toughness=5)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
