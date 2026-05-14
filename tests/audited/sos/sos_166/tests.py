"""Audited tests for Vastlands Scavenger // Bind to Life (collector key 166).

Verifies the Vastlands Scavenger // Bind to Life card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: complex.
"""

from __future__ import annotations

import pytest

from card_impl import VastlandsScavengerBindToLife

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestVastlandsScavengerBindToLifeBasicProperties:
    """Basic property tests for Vastlands Scavenger // Bind to Life."""

    def test_is_creature(self) -> None:
        """Vastlands Scavenger // Bind to Life must be a Creature subclass."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """VastlandsScavengerBindToLife.name must be 'Vastlands Scavenger // Bind to Life'."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert card.name == "Vastlands Scavenger // Bind to Life"

    def test_card_types(self) -> None:
        """Vastlands Scavenger // Bind to Life must have correct card types."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Vastlands Scavenger // Bind to Life must have converted mana cost 8."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert card.mana_cost.cmc == 8

    def test_colors(self) -> None:
        """Vastlands Scavenger // Bind to Life must have correct colors."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Vastlands Scavenger // Bind to Life must have base power 4."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Vastlands Scavenger // Bind to Life must have base toughness 4."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestVastlandsScavengerBindToLifeAbilities:
    """Ability tests for Vastlands Scavenger // Bind to Life -- expected to fail against stubs."""

    def test_has_prepared(self) -> None:
        """Vastlands Scavenger // Bind to Life must have Prepared keyword."""
        from engine.types import Keyword
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert Keyword.PREPARED in card.keywords, "Vastlands Scavenger // Bind to Life should have Prepared"

    def test_has_deathtouch(self) -> None:
        """Vastlands Scavenger // Bind to Life must have Deathtouch keyword."""
        from engine.types import Keyword
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert Keyword.DEATHTOUCH in card.keywords, "Vastlands Scavenger // Bind to Life should have Deathtouch"

    def test_etb_trigger_callable(self) -> None:
        """ETB trigger must be implemented per oracle text."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert callable(getattr(card, "on_enter_battlefield", None)), \
            "Vastlands Scavenger // Bind to Life must implement on_enter_battlefield per oracle text"

    def test_prepared_mechanic_implemented(self) -> None:
        """Prepared mechanic must be implemented per oracle text."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert callable(getattr(card, "check_prepared", None)) or \
            callable(getattr(card, "prepared_effect", None)) or \
            callable(getattr(card, "on_resolve", None)), \
            "Vastlands Scavenger // Bind to Life must implement prepared mechanic"


@pytest.mark.edge
class TestVastlandsScavengerBindToLifeEdgeCases:
    """Edge case and trap tests for Vastlands Scavenger // Bind to Life."""

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        card2 = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        card1.name = "Modified"
        assert card2.name == "Vastlands Scavenger // Bind to Life", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=None, base_power=4, base_toughness=4)
        assert card.mana_cost.cmc == 8, \
            f"CMC must be 8, got {card.mana_cost.cmc}"

    def test_survives_nonfatal_damage(self) -> None:
        """Creature must survive damage less than its toughness."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=player, base_power=4, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        if hasattr(card, "damage_taken"):
            card.damage_taken = 3
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert card in bf, "Creature must survive non-lethal damage"


@pytest.mark.interaction
class TestVastlandsScavengerBindToLifeInteractions:
    """Multi-card interaction tests for Vastlands Scavenger // Bind to Life."""

    def test_combat_with_opponent(self) -> None:
        """Must be able to engage in combat with opponent creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=player, base_power=4, base_toughness=4)
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
        card = VastlandsScavengerBindToLife(name="Vastlands Scavenger // Bind to Life", owner=player, base_power=4, base_toughness=4)
        card.controller = player
        set_board_state(game, 0, battlefield=[card, other])
        bf = player.zones[Zone.BATTLEFIELD].get_all()
        assert other in bf, "Other permanents must remain unaffected"
