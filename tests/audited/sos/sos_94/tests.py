"""Audited tests for Pox Plague (collector number 94).

Verifies the Pox Plague card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PoxPlague

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPoxPlagueBasicProperties:
    """Pox Plague basic property tests."""

    def test_is_sorcery(self) -> None:
        """Pox Plague must be a Sorcery subclass."""
        card = PoxPlague(name="Pox Plague", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """PoxPlague.name must be 'Pox Plague'."""
        card = PoxPlague(name="Pox Plague", owner=None)
        assert card.name == "Pox Plague"

    def test_card_type(self) -> None:
        """Pox Plague must have CardType.SORCERY."""
        card = PoxPlague(name="Pox Plague", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Pox Plague must have converted mana cost 5."""
        card = PoxPlague(name="Pox Plague", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Pox Plague must have colors ['B']."""
        card = PoxPlague(name="Pox Plague", owner=None)
        for c in ["B"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestPoxPlagueAbilities:
    """Pox Plague ability tests — expected to fail against stubs."""

    def test_on_resolve_causes_discard(self) -> None:
        """Pox Plague should cause discard on resolution.

        Oracle: Each player loses half their life, then discards half the cards in their hand, then sacrifices half 
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
        card = PoxPlague(name="Pox Plague", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(opponent.zones[Zone.HAND].get_all())
        assert hand_after < hand_before, (
            f"Expected opponent hand size to decrease. Before: {hand_before}, After: {hand_after}"
        )

    def test_on_resolve_causes_life_loss(self) -> None:
        """Pox Plague should cause life loss on resolution.

        Oracle: Each player loses half their life, then discards half the cards in their hand, then sacrifices half 
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game
        from engine.types import Zone

        game = create_game()
        player = game.players[0]
        life_before = player.life
        card = PoxPlague(name="Pox Plague", owner=player)
        card.controller = player
        card.on_resolve(game)
        assert player.life < life_before, (
            f"Expected life loss. Before: {life_before}, After: {player.life}"
        )

    def test_on_resolve_causes_sacrifice(self) -> None:
        """Pox Plague should cause sacrifice on resolution.

        Oracle: Each player loses half their life, then discards half the cards in their hand, then sacrifices half 
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        perms = [CardImpl(name=f"Perm{i}", owner=player) for i in range(4)]
        set_board_state(game, 0, battlefield=perms)
        bf_before = len(game.get_battlefield(player).get_all())
        card = PoxPlague(name="Pox Plague", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after < bf_before, (
            f"Expected sacrifice. Before: {bf_before}, After: {bf_after}"
        )
