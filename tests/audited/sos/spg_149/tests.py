"""Audited tests for Archaeomancer (collector key spg_149).

Verifies the Archaeomancer card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Archaeomancer

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestArchaeomancerBasicProperties:
    """Basic property tests for Archaeomancer."""

    def test_is_creature(self) -> None:
        """Archaeomancer must be a Creature subclass."""
        card = Archaeomancer(name="Archaeomancer", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """Archaeomancer.name must be 'Archaeomancer'."""
        card = Archaeomancer(name="Archaeomancer", owner=None)
        assert card.name == "Archaeomancer"

    def test_card_types(self) -> None:
        """Archaeomancer must have correct card types."""
        card = Archaeomancer(name="Archaeomancer", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Archaeomancer must have converted mana cost 4."""
        card = Archaeomancer(name="Archaeomancer", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Archaeomancer must have correct colors."""
        card = Archaeomancer(name="Archaeomancer", owner=None)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Archaeomancer must have base power 1."""
        card = Archaeomancer(name="Archaeomancer", owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Archaeomancer must have base toughness 2."""
        card = Archaeomancer(name="Archaeomancer", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestArchaeomancerAbilities:
    """Ability tests for Archaeomancer — expected to fail against stubs."""

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = Archaeomancer(name="Archaeomancer", owner=player)
        card.controller = player
        card._targets = [gy_card]
        if hasattr(card, "set_targets"):
            card.set_targets([gy_card])
        gy_before = len(player.zones[Zone.GRAVEYARD].get_all())
        card.on_resolve(game)
        gy_after = len(player.zones[Zone.GRAVEYARD].get_all())
        assert gy_after < gy_before, (
            f"Should return from gy: {gy_before} -> {gy_after}"
        )


@pytest.mark.edge
class TestArchaeomancerEdgeCases:
    """Edge case tests for Archaeomancer."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = Archaeomancer(name="Archaeomancer", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestArchaeomancerInteractions:
    """Interaction tests for Archaeomancer."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = Archaeomancer(name="Archaeomancer", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = Archaeomancer(name="Archaeomancer", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
