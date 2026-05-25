"""Audited tests for Silverquill, the Disputant (collector key 226).

Verifies the Silverquill, the Disputant card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import SilverquillTheDisputant

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.types import Keyword


@pytest.mark.basic
class TestSilverquillTheDisputantBasicProperties:
    """Basic property tests for Silverquill, the Disputant."""

    def test_is_creature(self) -> None:
        """Silverquill, the Disputant must be a Creature subclass."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """SilverquillTheDisputant.name must be 'Silverquill, the Disputant'."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert card.name == "Silverquill, the Disputant"

    def test_card_types(self) -> None:
        """Silverquill, the Disputant must have correct card types."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Silverquill, the Disputant must have converted mana cost 4."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Silverquill, the Disputant must have correct colors."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert "B" in card.colors
        assert "W" in card.colors

    def test_power(self) -> None:
        """Silverquill, the Disputant must have base power 4."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Silverquill, the Disputant must have base toughness 4."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert card.base_toughness == 4

    def test_has_flying_keyword(self) -> None:
        """Silverquill, the Disputant must have Flying keyword."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance_keyword(self) -> None:
        """Silverquill, the Disputant must have Vigilance keyword."""
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=None)
        assert Keyword.VIGILANCE in card.keywords


@pytest.mark.ability
class TestSilverquillTheDisputantAbilities:
    """Ability tests for Silverquill, the Disputant — expected to fail against stubs."""

    def test_on_resolve_changes_state(self) -> None:
        """Resolution must produce observable state change."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        from benchmarks.sos.workspace.engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=player)
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
class TestSilverquillTheDisputantEdgeCases:
    """Edge case tests for Silverquill, the Disputant."""

    def test_power_targeting_restriction(self) -> None:
        """Only targets creatures with power 1 or greater."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        small = Creature(name="Small", owner=opponent, base_power=0, base_toughness=2)
        big = Creature(name="Big", owner=opponent, base_power=1, base_toughness=2)
        set_board_state(game, 1, battlefield=[small, big])
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert big in targets, "Power >= 1 should be valid"
        assert small not in targets, "Power < 1 should be invalid"


@pytest.mark.interaction
class TestSilverquillTheDisputantInteractions:
    """Interaction tests for Silverquill, the Disputant."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = SilverquillTheDisputant(name="Silverquill, the Disputant", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
