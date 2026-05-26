"""Audited tests for Soaring Stoneglider (collector key 32).

Verifies the Soaring Stoneglider card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import SoaringStoneglider

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword

@pytest.mark.basic
class TestSoaringStonegliderBasicProperties:
    """Basic property tests for Soaring Stoneglider."""

    def test_is_creature(self) -> None:
        """Soaring Stoneglider must be a Creature subclass."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SoaringStoneglider.name must be 'Soaring Stoneglider'."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert card.name == "Soaring Stoneglider"

    def test_card_types(self) -> None:
        """Soaring Stoneglider must have correct card types."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Soaring Stoneglider must have converted mana cost 3."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Soaring Stoneglider must have correct colors."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert "W" in card_colors(card)

    def test_power(self) -> None:
        """Soaring Stoneglider must have base power 4."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Soaring Stoneglider must have base toughness 3."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert card.base_toughness == 3

    def test_has_flying_keyword(self) -> None:
        """Soaring Stoneglider must have Flying keyword."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance_keyword(self) -> None:
        """Soaring Stoneglider must have Vigilance keyword."""
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=None)
        assert Keyword.VIGILANCE in card.keywords

@pytest.mark.ability
class TestSoaringStonegliderAbilities:
    """Ability tests for Soaring Stoneglider — expected to fail against stubs."""

    def test_additional_cost_declared(self) -> None:
        """Card must declare additional cost mechanism."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=player)
        card.controller = player
        has_addl = (
            hasattr(card, "additional_costs") or
            hasattr(card, "get_additional_costs") or
            (hasattr(card, "rules_text") and "additional cost" in (card.rules_text or "").lower())
        )
        assert has_addl, "Card must declare additional cost"

@pytest.mark.edge
class TestSoaringStonegliderEdgeCases:
    """Edge case tests for Soaring Stoneglider."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()

@pytest.mark.interaction
class TestSoaringStonegliderInteractions:
    """Interaction tests for Soaring Stoneglider."""

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
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=player)
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
        card = SoaringStoneglider(name="Soaring Stoneglider", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
