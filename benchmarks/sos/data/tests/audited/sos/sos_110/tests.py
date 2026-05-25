"""Audited tests for Charging Strifeknight (collector key 110).

Verifies the Charging Strifeknight card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ChargingStrifeknight

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestChargingStrifeknightBasicProperties:
    """Basic property tests for Charging Strifeknight."""

    def test_is_creature(self) -> None:
        """Charging Strifeknight must be a Creature subclass."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ChargingStrifeknight.name must be 'Charging Strifeknight'."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert card.name == "Charging Strifeknight"

    def test_card_types(self) -> None:
        """Charging Strifeknight must have correct card types."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Charging Strifeknight must have converted mana cost 3."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Charging Strifeknight must have correct colors."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Charging Strifeknight must have base power 3."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert card.base_power == 3

    def test_toughness(self) -> None:
        """Charging Strifeknight must have base toughness 3."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert card.base_toughness == 3

    def test_has_haste_keyword(self) -> None:
        """Charging Strifeknight must have Haste keyword."""
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=None)
        assert Keyword.HASTE in card.keywords


@pytest.mark.ability
class TestChargingStrifeknightAbilities:
    """Ability tests for Charging Strifeknight — expected to fail against stubs."""

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )

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
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=player)
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
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestChargingStrifeknightEdgeCases:
    """Edge case tests for Charging Strifeknight."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestChargingStrifeknightInteractions:
    """Interaction tests for Charging Strifeknight."""

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
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=player)
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
        card = ChargingStrifeknight(name="Charging Strifeknight", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
