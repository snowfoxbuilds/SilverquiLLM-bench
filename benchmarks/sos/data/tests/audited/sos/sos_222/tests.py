"""Audited tests for Root Manipulation (collector number 222).

Verifies the Root Manipulation card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import RootManipulation

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost


@pytest.mark.basic
class TestRootManipulationBasicProperties:
    """Root Manipulation basic property tests."""

    def test_is_sorcery(self) -> None:
        """Root Manipulation must be a Sorcery subclass."""
        card = RootManipulation(name="Root Manipulation", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """RootManipulation.name must be 'Root Manipulation'."""
        card = RootManipulation(name="Root Manipulation", owner=None)
        assert card.name == "Root Manipulation"

    def test_card_type(self) -> None:
        """Root Manipulation must have CardType.SORCERY."""
        card = RootManipulation(name="Root Manipulation", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Root Manipulation must have converted mana cost 5."""
        card = RootManipulation(name="Root Manipulation", owner=None)
        assert card.mana_cost.cmc == 5

    def test_colors(self) -> None:
        """Root Manipulation must have colors ['B', 'G']."""
        card = RootManipulation(name="Root Manipulation", owner=None)
        for c in ["B", "G"]:
            assert c in card.colors, f"Expected color {c} in {card.colors}"


@pytest.mark.ability
class TestRootManipulationAbilities:
    """Root Manipulation ability tests — expected to fail against stubs."""

    def test_on_resolve_grants_buff(self) -> None:
        """Root Manipulation should grant a buff until end of turn.

        Oracle: Until end of turn, creatures you control get +2/+2 and gain menace and "Whenever this creature attac
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from benchmarks.sos.workspace.engine.card import Creature as CreatureBase

        game = create_game()
        player = game.players[0]
        target = CreatureBase(name="TestCreature", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        power_before = target.power
        card = RootManipulation(name="Root Manipulation", owner=player)
        card.controller = player
        card.on_resolve(game)
        # A correct implementation should modify creature power
        assert target.power > power_before, (
            f"Expected power increase. Before: {power_before}, After: {target.power}"
        )
