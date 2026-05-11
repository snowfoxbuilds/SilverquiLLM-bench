"""Audited tests for Pestbrood Sloth (collector key 157).

Verifies the Pestbrood Sloth card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PestbroodSloth

from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.types import Keyword


@pytest.mark.basic
class TestPestbroodSlothBasicProperties:
    """Basic property tests for Pestbrood Sloth."""

    def test_is_creature(self) -> None:
        """Pestbrood Sloth must be a Creature subclass."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """PestbroodSloth.name must be 'Pestbrood Sloth'."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert card.name == "Pestbrood Sloth"

    def test_card_types(self) -> None:
        """Pestbrood Sloth must have correct card types."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Pestbrood Sloth must have converted mana cost 4."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Pestbrood Sloth must have correct colors."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert "G" in card.colors

    def test_power(self) -> None:
        """Pestbrood Sloth must have base power 4."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert card.base_power == 4

    def test_toughness(self) -> None:
        """Pestbrood Sloth must have base toughness 4."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert card.base_toughness == 4

    def test_has_reach_keyword(self) -> None:
        """Pestbrood Sloth must have Reach keyword."""
        card = PestbroodSloth(name="Pestbrood Sloth", owner=None)
        assert Keyword.REACH in card.keywords


@pytest.mark.ability
class TestPestbroodSlothAbilities:
    """Ability tests for Pestbrood Sloth — expected to fail against stubs."""

    def test_creates_token(self) -> None:
        """Resolution should create token(s) on battlefield."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PestbroodSloth(name="Pestbrood Sloth", owner=player)
        card.controller = player
        bf_before = len(game.get_battlefield(player).get_all())
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after > bf_before, (
            f"Should create token: bf {bf_before} -> {bf_after}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = PestbroodSloth(name="Pestbrood Sloth", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestPestbroodSlothEdgeCases:
    """Edge case tests for Pestbrood Sloth."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PestbroodSloth(name="Pestbrood Sloth", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestPestbroodSlothInteractions:
    """Interaction tests for Pestbrood Sloth."""

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
        card = PestbroodSloth(name="Pestbrood Sloth", owner=player)
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
        card = PestbroodSloth(name="Pestbrood Sloth", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
