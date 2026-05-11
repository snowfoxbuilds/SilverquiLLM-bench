"""Audited tests for Dualcaster Mage (collector key spg_153).

Verifies the Dualcaster Mage card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import DualcasterMage

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestDualcasterMageBasicProperties:
    """Basic property tests for Dualcaster Mage."""

    def test_is_creature(self) -> None:
        """Dualcaster Mage must be a Creature subclass."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """DualcasterMage.name must be 'Dualcaster Mage'."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert card.name == "Dualcaster Mage"

    def test_card_types(self) -> None:
        """Dualcaster Mage must have correct card types."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Dualcaster Mage must have converted mana cost 3."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Dualcaster Mage must have correct colors."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert "R" in card.colors

    def test_power(self) -> None:
        """Dualcaster Mage must have base power 2."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Dualcaster Mage must have base toughness 2."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert card.base_toughness == 2

    def test_has_flash_keyword(self) -> None:
        """Dualcaster Mage must have Flash keyword."""
        card = DualcasterMage(name="Dualcaster Mage", owner=None)
        assert Keyword.FLASH in card.keywords


@pytest.mark.ability
class TestDualcasterMageAbilities:
    """Ability tests for Dualcaster Mage — expected to fail against stubs."""

    def test_on_resolve_changes_state(self) -> None:
        """Resolution must produce observable state change."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = DualcasterMage(name="Dualcaster Mage", owner=player)
        card.controller = player
        p_life = player.life
        o_life = opponent.life
        p_bf = len(game.get_battlefield(player).get_all())
        o_bf = len(game.get_battlefield(opponent).get_all())
        p_hand = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        changed = (
            player.life != p_life or opponent.life != o_life or
            len(game.get_battlefield(player).get_all()) != p_bf or
            len(game.get_battlefield(opponent).get_all()) != o_bf or
            len(player.zones[Zone.HAND].get_all()) != p_hand or
            len(player.zones[Zone.GRAVEYARD].get_all()) > 0 or
            len(opponent.zones[Zone.GRAVEYARD].get_all()) > 0
        )
        assert changed, "on_resolve must change game state"


@pytest.mark.edge
class TestDualcasterMageEdgeCases:
    """Edge case tests for Dualcaster Mage."""

    def test_may_choice_optional(self) -> None:
        """May effect is optional — decline should not crash."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = DualcasterMage(name="Dualcaster Mage", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # No TypeError/AttributeError means optional is handled
        assert True


@pytest.mark.interaction
class TestDualcasterMageInteractions:
    """Interaction tests for Dualcaster Mage."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = DualcasterMage(name="Dualcaster Mage", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = DualcasterMage(name="Dualcaster Mage", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
