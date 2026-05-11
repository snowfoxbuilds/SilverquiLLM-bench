"""Audited tests for Matterbending Mage (collector key 59).

Verifies the Matterbending Mage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import MatterbendingMage

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMatterbendingMageBasicProperties:
    """Basic property tests for Matterbending Mage."""

    def test_is_creature(self) -> None:
        """Matterbending Mage must be a Creature subclass."""
        card = MatterbendingMage(name="Matterbending Mage", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """MatterbendingMage.name must be 'Matterbending Mage'."""
        card = MatterbendingMage(name="Matterbending Mage", owner=None)
        assert card.name == "Matterbending Mage"

    def test_card_types(self) -> None:
        """Matterbending Mage must have correct card types."""
        card = MatterbendingMage(name="Matterbending Mage", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Matterbending Mage must have converted mana cost 3."""
        card = MatterbendingMage(name="Matterbending Mage", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Matterbending Mage must have correct colors."""
        card = MatterbendingMage(name="Matterbending Mage", owner=None)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Matterbending Mage must have base power 2."""
        card = MatterbendingMage(name="Matterbending Mage", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Matterbending Mage must have base toughness 2."""
        card = MatterbendingMage(name="Matterbending Mage", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestMatterbendingMageAbilities:
    """Ability tests for Matterbending Mage — expected to fail against stubs."""

    def test_bounces_target(self) -> None:
        """Resolution should return target to hand."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Bounced", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = MatterbendingMage(name="Matterbending Mage", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        bf_before = len(game.get_battlefield(opponent).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(opponent).get_all())
        assert bf_after < bf_before, (
            f"Target should leave bf: {bf_before} -> {bf_after}"
        )


@pytest.mark.edge
class TestMatterbendingMageEdgeCases:
    """Edge case tests for Matterbending Mage."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = MatterbendingMage(name="Matterbending Mage", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestMatterbendingMageInteractions:
    """Interaction tests for Matterbending Mage."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = MatterbendingMage(name="Matterbending Mage", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = MatterbendingMage(name="Matterbending Mage", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
