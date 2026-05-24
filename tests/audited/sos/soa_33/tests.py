"""Audited tests for Smallpox (SOA collector number 33).

Verifies the Smallpox card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Smallpox

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestSmallpoxBasicProperties:
    """Smallpox basic property tests."""

    def test_is_sorcery(self) -> None:
        """Smallpox must be a Sorcery subclass."""
        card = Smallpox(name="Smallpox", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """Smallpox.name must be 'Smallpox'."""
        card = Smallpox(name="Smallpox", owner=None)
        assert card.name == "Smallpox"

    def test_card_type(self) -> None:
        """Smallpox must have CardType.SORCERY."""
        card = Smallpox(name="Smallpox", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Smallpox must have converted mana cost 2."""
        card = Smallpox(name="Smallpox", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Smallpox must have colors ['B']."""
        card = Smallpox(name="Smallpox", owner=None)
        for c in ["B"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestSmallpoxAbilities:
    """Smallpox ability tests — expected to fail against stubs."""

    def test_on_resolve_causes_discard(self) -> None:
        """Smallpox should cause discard on resolution.

        Oracle: Each player loses 1 life, discards a card, sacrifices a creature of their choice, then sacrifices a 
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        # Give opponent cards in hand
        hand_cards = [CardImpl(name=f"HandCard{i}", owner=opponent) for i in range(4)]
        set_board_state(game, 1, hand=hand_cards)
        hand_before = len(opponent.zones[Zone.HAND].get_all())
        card = Smallpox(name="Smallpox", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Expected opponent hand size to decrease. Before: {hand_before}, After: {hand_after}"
        )

    def test_on_resolve_causes_life_loss(self) -> None:
        """Smallpox should cause life loss on resolution.

        Oracle: Each player loses 1 life, discards a card, sacrifices a creature of their choice, then sacrifices a 
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        life_before = player.life
        card = Smallpox(name="Smallpox", owner=player)
        card.controller = player
        card.on_resolve(game)
        assert player.life < life_before, (
            f"Expected life loss. Before: {life_before}, After: {player.life}"
        )

    def test_on_resolve_causes_sacrifice(self) -> None:
        """Smallpox should cause each player to sacrifice a creature and a land.

        Oracle: Each player loses 1 life, discards a card, sacrifices a creature of their choice, then sacrifices a land of their choice.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import Creature as CreatureBase, Land

        game = create_game()
        player = game.players[0]
        creature = CreatureBase(name="SacCreature", owner=player, base_power=1, base_toughness=1)
        land = Land(name="SacLand", owner=player)
        set_board_state(game, 0, battlefield=[creature, land])
        card = Smallpox(name="Smallpox", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf_after = game.get_battlefield(player).get_all()
        assert creature not in bf_after, (
            f"Expected creature to be sacrificed. BF: {[c.name for c in bf_after]}"
        )
        assert land not in bf_after, (
            f"Expected land to be sacrificed. BF: {[c.name for c in bf_after]}"
        )
