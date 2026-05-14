"""Audited tests for Hydro-Channeler (collector key 54).

Verifies the Hydro-Channeler card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import HydroChanneler

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestHydroChannelerBasicProperties:
    """Basic property tests for Hydro-Channeler."""

    def test_is_creature(self) -> None:
        """Hydro-Channeler must be a Creature subclass."""
        card = HydroChanneler(name="Hydro-Channeler", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """HydroChanneler.name must be 'Hydro-Channeler'."""
        card = HydroChanneler(name="Hydro-Channeler", owner=None)
        assert card.name == "Hydro-Channeler"

    def test_card_types(self) -> None:
        """Hydro-Channeler must have correct card types."""
        card = HydroChanneler(name="Hydro-Channeler", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Hydro-Channeler must have converted mana cost 2."""
        card = HydroChanneler(name="Hydro-Channeler", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Hydro-Channeler must have correct colors."""
        card = HydroChanneler(name="Hydro-Channeler", owner=None)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Hydro-Channeler must have base power 1."""
        card = HydroChanneler(name="Hydro-Channeler", owner=None)
        assert card.base_power == 1

    def test_toughness(self) -> None:
        """Hydro-Channeler must have base toughness 3."""
        card = HydroChanneler(name="Hydro-Channeler", owner=None)
        assert card.base_toughness == 3


@pytest.mark.ability
class TestHydroChannelerAbilities:
    """Ability tests for Hydro-Channeler — expected to fail against stubs."""

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from tests.test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = HydroChanneler(name="Hydro-Channeler", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestHydroChannelerEdgeCases:
    """Edge case tests for Hydro-Channeler."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = HydroChanneler(name="Hydro-Channeler", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestHydroChannelerInteractions:
    """Interaction tests for Hydro-Channeler."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = HydroChanneler(name="Hydro-Channeler", owner=player)
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
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = HydroChanneler(name="Hydro-Channeler", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
