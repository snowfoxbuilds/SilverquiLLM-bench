"""Audited tests for Arnyn, Deathbloom Botanist (collector key 74).

Verifies the Arnyn, Deathbloom Botanist card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ArnynDeathbloomBotanist

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestArnynDeathbloomBotanistBasicProperties:
    """Basic property tests for Arnyn, Deathbloom Botanist."""

    def test_is_creature(self) -> None:
        """Arnyn, Deathbloom Botanist must be a Creature subclass."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ArnynDeathbloomBotanist.name must be 'Arnyn, Deathbloom Botanist'."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert card.name == "Arnyn, Deathbloom Botanist"

    def test_card_types(self) -> None:
        """Arnyn, Deathbloom Botanist must have correct card types."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Arnyn, Deathbloom Botanist must have converted mana cost 3."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Arnyn, Deathbloom Botanist must have correct colors."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Arnyn, Deathbloom Botanist must have base power 2."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Arnyn, Deathbloom Botanist must have base toughness 2."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert card.base_toughness == 2

    def test_has_deathtouch_keyword(self) -> None:
        """Arnyn, Deathbloom Botanist must have Deathtouch keyword."""
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=None)
        assert Keyword.DEATHTOUCH in card.keywords


@pytest.mark.ability
class TestArnynDeathbloomBotanistAbilities:
    """Ability tests for Arnyn, Deathbloom Botanist — expected to fail against stubs."""

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

    def test_causes_life_loss(self) -> None:
        """Resolution should cause life loss."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=player)
        card.controller = player
        life_before = opponent.life
        card.on_resolve(game)
        assert opponent.life < life_before, (
            f"Should lose life: {life_before} -> {opponent.life}"
        )


@pytest.mark.edge
class TestArnynDeathbloomBotanistEdgeCases:
    """Edge case tests for Arnyn, Deathbloom Botanist."""

    def test_targets_only_own_permanents(self) -> None:
        """Should only target permanents you control."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        own = Creature(name="Own", owner=player, base_power=2, base_toughness=2)
        enemy = Creature(name="Enemy", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[own])
        set_board_state(game, 1, battlefield=[enemy])
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        if len(targets) > 0:
            assert own in targets, "Own creature should be valid"
            assert enemy not in targets, "Opponent creature should be invalid"


@pytest.mark.interaction
class TestArnynDeathbloomBotanistInteractions:
    """Interaction tests for Arnyn, Deathbloom Botanist."""

    def test_get_targets_finds_own_creatures(self) -> None:
        """get_targets should return valid own creatures."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        creature = Creature(name="Mine", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find own creature as target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = ArnynDeathbloomBotanist(name="Arnyn, Deathbloom Botanist", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
