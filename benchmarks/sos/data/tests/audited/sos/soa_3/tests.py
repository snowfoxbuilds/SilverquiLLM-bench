"""Audited tests for Armageddon (SOA collector number 3).

Verifies the Armageddon card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Armageddon

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestArmageddonBasicProperties:
    """Armageddon basic property tests."""

    def test_is_sorcery(self) -> None:
        """Armageddon must be a Sorcery subclass."""
        card = Armageddon(name="Armageddon", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """Armageddon.name must be 'Armageddon'."""
        card = Armageddon(name="Armageddon", owner=None)
        assert card.name == "Armageddon"

    def test_card_type(self) -> None:
        """Armageddon must have CardType.SORCERY."""
        card = Armageddon(name="Armageddon", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Armageddon must have converted mana cost 4."""
        card = Armageddon(name="Armageddon", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Armageddon must have colors ['W']."""
        card = Armageddon(name="Armageddon", owner=None)
        for c in ["W"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestArmageddonAbilities:
    """Armageddon ability tests — expected to fail against stubs."""

    def test_on_resolve_destroys_permanents(self) -> None:
        """Armageddon should destroy permanents on resolution.

        Oracle: Destroy all lands.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.types import Zone
        from benchmarks.sos.workspace.engine.card import CardImpl

        game = create_game()
        player = game.players[0]
        # Place some permanents on the battlefield
        targets = []
        for i in range(3):
            t = CardImpl(name=f"Target{i}", owner=player)
            targets.append(t)
        set_board_state(game, 0, battlefield=targets)
        bf_before = len(game.get_battlefield(player).get_all())
        card = Armageddon(name="Armageddon", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf_after = len(game.get_battlefield(player).get_all())
        assert bf_after < bf_before, (
            f"Expected permanents destroyed. Before: {bf_before}, After: {bf_after}"
        )
