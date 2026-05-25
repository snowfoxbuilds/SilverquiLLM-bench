"""Audited tests for Aziza, Mage Tower Captain (collector key 174).

Verifies the Aziza, Mage Tower Captain card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import AzizaMageTowerCaptain

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestAzizaMageTowerCaptainBasicProperties:
    """Basic property tests for Aziza, Mage Tower Captain."""

    def test_is_creature(self) -> None:
        """Aziza, Mage Tower Captain must be a Creature subclass."""
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """AzizaMageTowerCaptain.name must be 'Aziza, Mage Tower Captain'."""
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=None)
        assert card.name == "Aziza, Mage Tower Captain"

    def test_card_types(self) -> None:
        """Aziza, Mage Tower Captain must have correct card types."""
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Aziza, Mage Tower Captain must have converted mana cost 2."""
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Aziza, Mage Tower Captain must have correct colors."""
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=None)
        assert "R" in card.colors
        assert "W" in card.colors

    def test_power(self) -> None:
        """Aziza, Mage Tower Captain must have base power 2."""
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Aziza, Mage Tower Captain must have base toughness 2."""
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestAzizaMageTowerCaptainAbilities:
    """Ability tests for Aziza, Mage Tower Captain — expected to fail against stubs."""

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
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=player)
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
class TestAzizaMageTowerCaptainEdgeCases:
    """Edge case tests for Aziza, Mage Tower Captain."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestAzizaMageTowerCaptainInteractions:
    """Interaction tests for Aziza, Mage Tower Captain."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = AzizaMageTowerCaptain(name="Aziza, Mage Tower Captain", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
