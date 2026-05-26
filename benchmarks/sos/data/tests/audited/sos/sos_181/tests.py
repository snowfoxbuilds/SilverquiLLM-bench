"""Audited tests for Colossus of the Blood Age (collector key 181).

Verifies the Colossus of the Blood Age card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

from test_utils import card_colors

import pytest

from card_impl import ColossusOfTheBloodAge

from engine.card import Creature
from engine.types import CardType, ManaCost

@pytest.mark.basic
class TestColossusOfTheBloodAgeBasicProperties:
    """Basic property tests for Colossus of the Blood Age."""

    def test_is_creature(self) -> None:
        """Colossus of the Blood Age must be a Creature subclass."""
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """ColossusOfTheBloodAge.name must be 'Colossus of the Blood Age'."""
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=None)
        assert card.name == "Colossus of the Blood Age"

    def test_card_types(self) -> None:
        """Colossus of the Blood Age must have correct card types."""
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Colossus of the Blood Age must have converted mana cost 6."""
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=None)
        assert card.mana_cost.cmc == 6

    def test_colors(self) -> None:
        """Colossus of the Blood Age must have correct colors."""
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=None)
        assert "R" in card_colors(card)
        assert "W" in card_colors(card)

    def test_power(self) -> None:
        """Colossus of the Blood Age must have base power 6."""
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=None)
        assert card.base_power == 6

    def test_toughness(self) -> None:
        """Colossus of the Blood Age must have base toughness 6."""
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=None)
        assert card.base_toughness == 6

@pytest.mark.ability
class TestColossusOfTheBloodAgeAbilities:
    """Ability tests for Colossus of the Blood Age — expected to fail against stubs."""

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
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Should discard: hand {hand_before} -> {hand_after}"
        )

    def test_deals_damage(self) -> None:
        """Resolution should deal 3 damage."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        life_before = opponent.life
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=player)
        card.controller = player
        card._targets = [opponent]
        if hasattr(card, "set_targets"):
            card.set_targets([opponent])
        card.on_resolve(game)
        life_after = opponent.life
        assert life_after < life_before, (
            f"Should deal damage: life {life_before} -> {life_after}"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )

@pytest.mark.edge
class TestColossusOfTheBloodAgeEdgeCases:
    """Edge case tests for Colossus of the Blood Age."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()

@pytest.mark.interaction
class TestColossusOfTheBloodAgeInteractions:
    """Interaction tests for Colossus of the Blood Age."""

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
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=player)
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
        card = ColossusOfTheBloodAge(name="Colossus of the Blood Age", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
