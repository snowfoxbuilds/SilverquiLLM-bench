"""Audited tests for Summoned Dromedary (collector key 37).

Verifies the Summoned Dromedary card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SummonedDromedary

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestSummonedDromedaryBasicProperties:
    """Basic property tests for Summoned Dromedary."""

    def test_is_creature(self) -> None:
        """Summoned Dromedary must be a Creature subclass."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SummonedDromedary.name must be 'Summoned Dromedary'."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert card.name == "Summoned Dromedary"

    def test_card_types(self) -> None:
        """Summoned Dromedary must have correct card types."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Summoned Dromedary must have converted mana cost 4."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Summoned Dromedary must have correct colors."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert "W" in card.colors

    def test_power(self) -> None:
        """Summoned Dromedary must have base power 4."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Summoned Dromedary must have base toughness 3."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert card.base_toughness == 3

    def test_has_vigilance_keyword(self) -> None:
        """Summoned Dromedary must have Vigilance keyword."""
        card = SummonedDromedary(name="Summoned Dromedary", owner=None)
        assert Keyword.VIGILANCE in card.keywords


@pytest.mark.ability
class TestSummonedDromedaryAbilities:
    """Ability tests for Summoned Dromedary — expected to fail against stubs."""

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = SummonedDromedary(name="Summoned Dromedary", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"

    def test_returns_from_graveyard(self) -> None:
        """Resolution should return card from graveyard."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        gy_card = Creature(name="Returned", owner=player, base_power=1, base_toughness=1)
        set_board_state(game, 0, graveyard=[gy_card])
        card = SummonedDromedary(name="Summoned Dromedary", owner=player)
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
class TestSummonedDromedaryEdgeCases:
    """Edge case tests for Summoned Dromedary."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = SummonedDromedary(name="Summoned Dromedary", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestSummonedDromedaryInteractions:
    """Interaction tests for Summoned Dromedary."""

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
        card = SummonedDromedary(name="Summoned Dromedary", owner=player)
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
        card = SummonedDromedary(name="Summoned Dromedary", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
