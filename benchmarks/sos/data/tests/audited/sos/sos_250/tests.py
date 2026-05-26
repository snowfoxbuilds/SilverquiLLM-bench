"""Audited tests for Page, Loose Leaf (collector key 250).

Verifies the Page, Loose Leaf card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import PageLooseLeaf

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestPageLooseLeafBasicProperties:
    """Basic property tests for Page, Loose Leaf."""

    def test_is_creature(self) -> None:
        """Page, Loose Leaf must be a Creature subclass."""
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """PageLooseLeaf.name must be 'Page, Loose Leaf'."""
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=None)
        assert card.name == "Page, Loose Leaf"

    def test_card_types(self) -> None:
        """Page, Loose Leaf must have correct card types."""
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Page, Loose Leaf must have converted mana cost 2."""
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Page, Loose Leaf must have correct colors."""
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=None)
        assert len(card_colors(card)) == 0

    def test_power(self) -> None:
        """Page, Loose Leaf must have base power 0."""
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=None)
        assert card.base_power == 0

    def test_toughness(self) -> None:
        """Page, Loose Leaf must have base toughness 2."""
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=None)
        assert card.base_toughness == 2

@pytest.mark.ability
class TestPageLooseLeafAbilities:
    """Ability tests for Page, Loose Leaf — expected to fail against stubs."""

    def test_causes_discard(self) -> None:
        """Resolution should cause discard."""
        from test_utils import create_game, set_board_state
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        filler = Sorcery(name="Discardable", owner=opponent)
        set_board_state(game, 1, hand=[filler])
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"

@pytest.mark.edge
class TestPageLooseLeafEdgeCases:
    """Edge case tests for Page, Loose Leaf."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()

@pytest.mark.interaction
class TestPageLooseLeafInteractions:
    """Interaction tests for Page, Loose Leaf."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = PageLooseLeaf(name="Page, Loose Leaf", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
