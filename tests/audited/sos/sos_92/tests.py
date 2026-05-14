"""Audited tests for Poisoner's Apprentice (collector key 92).

Verifies the Poisoner's Apprentice card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PoisonersApprentice

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPoisonersApprenticeBasicProperties:
    """Basic property tests for Poisoner's Apprentice."""

    def test_is_creature(self) -> None:
        """Poisoner's Apprentice must be a Creature subclass."""
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """PoisonersApprentice.name must be 'Poisoner's Apprentice'."""
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=None)
        assert card.name == "Poisoner's Apprentice"

    def test_card_types(self) -> None:
        """Poisoner's Apprentice must have correct card types."""
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Poisoner's Apprentice must have converted mana cost 3."""
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Poisoner's Apprentice must have correct colors."""
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=None)
        assert "B" in card.colors

    def test_power(self) -> None:
        """Poisoner's Apprentice must have base power 2."""
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Poisoner's Apprentice must have base toughness 2."""
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestPoisonersApprenticeAbilities:
    """Ability tests for Poisoner's Apprentice — expected to fail against stubs."""

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestPoisonersApprenticeEdgeCases:
    """Edge case tests for Poisoner's Apprentice."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestPoisonersApprenticeInteractions:
    """Interaction tests for Poisoner's Apprentice."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = PoisonersApprentice(name="Poisoner's Apprentice", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
