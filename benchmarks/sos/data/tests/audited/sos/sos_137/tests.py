"""Audited tests for Zealous Lorecaster (collector key 137).

Verifies the Zealous Lorecaster card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ZealousLorecaster

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestZealousLorecasterBasicProperties:
    """Basic property tests for Zealous Lorecaster."""

    def test_is_creature(self) -> None:
        """Zealous Lorecaster must be a Creature subclass."""
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ZealousLorecaster.name must be 'Zealous Lorecaster'."""
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=None)
        assert card.name == "Zealous Lorecaster"

    def test_card_types(self) -> None:
        """Zealous Lorecaster must have correct card types."""
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Zealous Lorecaster must have converted mana cost 6."""
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=None)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Zealous Lorecaster must have correct colors."""
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=None)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Zealous Lorecaster must have base power 4."""
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Zealous Lorecaster must have base toughness 4."""
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=None)
        assert card.base_toughness == 4


@pytest.mark.ability
class TestZealousLorecasterAbilities:
    """Ability tests for Zealous Lorecaster — expected to fail against stubs."""

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=player)
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
class TestZealousLorecasterEdgeCases:
    """Edge case tests for Zealous Lorecaster."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestZealousLorecasterInteractions:
    """Interaction tests for Zealous Lorecaster."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = ZealousLorecaster(name="Zealous Lorecaster", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
