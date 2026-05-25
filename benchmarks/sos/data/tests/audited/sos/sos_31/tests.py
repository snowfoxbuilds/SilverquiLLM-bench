"""Audited tests for Shattered Acolyte (collector key 31).

Verifies the Shattered Acolyte card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import ShatteredAcolyte

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestShatteredAcolyteBasicProperties:
    """Basic property tests for Shattered Acolyte."""

    def test_is_creature(self) -> None:
        """Shattered Acolyte must be a Creature subclass."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ShatteredAcolyte.name must be 'Shattered Acolyte'."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert card.name == "Shattered Acolyte"

    def test_card_types(self) -> None:
        """Shattered Acolyte must have correct card types."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Shattered Acolyte must have converted mana cost 2."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Shattered Acolyte must have correct colors."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert "W" in card.colors

    def test_power(self) -> None:
        """Shattered Acolyte must have base power 2."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Shattered Acolyte must have base toughness 2."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert card.base_toughness == 2

    def test_has_lifelink_keyword(self) -> None:
        """Shattered Acolyte must have Lifelink keyword."""
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=None)
        assert Keyword.LIFELINK in card.keywords


@pytest.mark.ability
class TestShatteredAcolyteAbilities:
    """Ability tests for Shattered Acolyte — expected to fail against stubs."""

    def test_destroys_target(self) -> None:
        """Resolution should destroy the target."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Doomed", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        bf_before = len(game.get_battlefield(opponent).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(opponent).get_all())
        assert bf_after < bf_before, (
            f"Target should be destroyed: bf {bf_before} -> {bf_after}"
        )

    def test_has_activated_ability(self) -> None:
        """Card must expose at least one activated ability."""
        from test_utils import create_game, set_board_state
        game = create_game()
        player = game.players[0]
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        abilities_list = card.get_activated_abilities()
        assert len(abilities_list) > 0, "Card must have activated ability"


@pytest.mark.edge
class TestShatteredAcolyteEdgeCases:
    """Edge case tests for Shattered Acolyte."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestShatteredAcolyteInteractions:
    """Interaction tests for Shattered Acolyte."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = ShatteredAcolyte(name="Shattered Acolyte", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
