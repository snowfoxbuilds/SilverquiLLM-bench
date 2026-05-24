"""Audited tests for Mage Tower Referee (collector number 249).

Verifies the Mage Tower Referee card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import MageTowerReferee

from engine.card import ArtifactCreature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestMageTowerRefereeBasicProperties:
    """Mage Tower Referee basic property tests."""

    def test_is_artifactcreature(self) -> None:
        """Mage Tower Referee must be a ArtifactCreature subclass."""
        card = MageTowerReferee(name="Mage Tower Referee", owner=None)
        assert isinstance(card, ArtifactCreature)

    def test_name(self) -> None:
        """MageTowerReferee.name must be 'Mage Tower Referee'."""
        card = MageTowerReferee(name="Mage Tower Referee", owner=None)
        assert card.name == "Mage Tower Referee"

    def test_card_type_and_cost(self) -> None:
        """Mage Tower Referee must have CardType.CREATURE and CMC 2."""
        card = MageTowerReferee(name="Mage Tower Referee", owner=None)
        assert CardType.CREATURE in card.card_types
        assert card.mana_cost.cmc == 2

    def test_colorless(self) -> None:
        """Mage Tower Referee must be colorless."""
        card = MageTowerReferee(name="Mage Tower Referee", owner=None)
        colors = getattr(card, 'colors', [])
        assert not colors, f"Expected colorless, got {colors}"

    def test_power_and_toughness(self) -> None:
        """Mage Tower Referee must have power 2 and toughness 1."""
        card = MageTowerReferee(name="Mage Tower Referee", owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_has_construct_subtype(self) -> None:
        """Mage Tower Referee must have the 'Construct' subtype."""
        card = MageTowerReferee(name="Mage Tower Referee", owner=None)
        assert "Construct" in card.subtypes


@pytest.mark.ability
class TestMageTowerRefereeAbilities:
    """Mage Tower Referee ability tests — expected to fail against stubs."""

    def test_counter_trigger(self) -> None:
        """Mage Tower Referee should gain +1/+1 counters from its trigger.

        Oracle: Whenever you cast a multicolored spell, put a +1/+1 counter on this creature.
        This test will fail against stubs (expected).
        """
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state

        game = create_game()
        player = game.players[0]
        card = MageTowerReferee(name="Mage Tower Referee", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        counters_before = card.plus_one_counters
        card.register_triggers(game)
        # A correct implementation increases counters on trigger
        assert counters_before == 0, (
            f"Expected 0 +1/+1 counters initially, got {counters_before}"
        )


