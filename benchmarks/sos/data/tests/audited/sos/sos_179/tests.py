"""Audited tests for Cauldron of Essence (collector key 179).

Verifies the Cauldron of Essence card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import CauldronOfEssence

from engine.card import Artifact
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestCauldronOfEssenceBasicProperties:
    """Basic property tests for Cauldron of Essence."""

    def test_is_artifact(self) -> None:
        """Cauldron of Essence must be a Artifact subclass."""
        card = CauldronOfEssence(name="Cauldron of Essence", owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        """CauldronOfEssence.name must be 'Cauldron of Essence'."""
        card = CauldronOfEssence(name="Cauldron of Essence", owner=None)
        assert card.name == "Cauldron of Essence"

    def test_card_types(self) -> None:
        """Cauldron of Essence must have correct card types."""
        card = CauldronOfEssence(name="Cauldron of Essence", owner=None)
        assert CardType.ARTIFACT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Cauldron of Essence must have converted mana cost 3."""
        card = CauldronOfEssence(name="Cauldron of Essence", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Cauldron of Essence must have correct colors."""
        card = CauldronOfEssence(name="Cauldron of Essence", owner=None)
        assert "B" in card_colors(card)
        assert "G" in card_colors(card)

@pytest.mark.ability
class TestCauldronOfEssenceAbilities:
    """Ability tests for Cauldron of Essence — expected to fail against stubs."""

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CauldronOfEssence(name="Cauldron of Essence", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

    def test_causes_life_loss(self) -> None:
        """Resolution should cause life loss."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = CauldronOfEssence(name="Cauldron of Essence", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = CauldronOfEssence(name="Cauldron of Essence", owner=player)
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
        card = CauldronOfEssence(name="Cauldron of Essence", owner=player)
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
class TestCauldronOfEssenceEdgeCases:
    """Edge case tests for Cauldron of Essence."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = CauldronOfEssence(name="Cauldron of Essence", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"

@pytest.mark.interaction
class TestCauldronOfEssenceInteractions:
    """Interaction tests for Cauldron of Essence."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = CauldronOfEssence(name="Cauldron of Essence", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = CauldronOfEssence(name="Cauldron of Essence", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
