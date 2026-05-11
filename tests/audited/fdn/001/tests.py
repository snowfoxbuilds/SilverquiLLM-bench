"""Audited tests for Plains (FDN collector number 001).

Verifies the Plains card implementation through the ``card_impl`` module
injection mechanism provided by the FDN conftest.

Uses category markers per audited-test conventions:
- @pytest.mark.basic — fundamental card properties
- @pytest.mark.mana — mana ability tests
"""

from __future__ import annotations

import pytest

from card_impl import Plains

from engine.card import Land
from engine.types import ManaType, Supertype


@pytest.mark.basic
class TestPlainsBasicProperties:
    """Basic property tests for the Plains card."""

    def test_plains_is_land(self) -> None:
        """Plains must be a Land subclass."""
        card = Plains(name="Plains", owner=None)
        assert isinstance(card, Land)

    def test_plains_has_basic_supertype(self) -> None:
        """Plains must have the BASIC supertype."""
        card = Plains(name="Plains", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_plains_has_plains_subtype(self) -> None:
        """Plains must have the 'Plains' land subtype."""
        card = Plains(name="Plains", owner=None)
        assert "Plains" in card.subtypes

    def test_plains_name(self) -> None:
        """Plains.name must be 'Plains'."""
        card = Plains(name="Plains", owner=None)
        assert card.name == "Plains"

    def test_enters_untapped(self) -> None:
        """Plains enters the battlefield untapped."""
        card = Plains(name="Plains", owner=None)
        assert not card.is_tapped


@pytest.mark.mana
class TestPlainsManaAbility:
    """Mana ability tests for Plains."""

    def test_plains_taps_for_white_mana(self) -> None:
        """Plains must have a mana ability producing {W}."""
        card = Plains(name="Plains", owner=None)
        mana_abilities = card.get_mana_abilities()
        assert len(mana_abilities) > 0
        assert "{W}" in mana_abilities[0].description

    def test_tapping_produces_white_mana(self) -> None:
        """Activating Plains mana ability adds {W} to controller's mana pool."""
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        card = Plains(name="Plains", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        cost_paid = abilities[0].cost(game, card)
        assert cost_paid
        assert card.is_tapped
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.WHITE) >= 1

    def test_untap_after_tapping(self) -> None:
        """Plains untaps when the untap function is called after being tapped."""
        from engine.game import untap
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        card = Plains(name="Plains", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])
        # Tap the land via mana ability
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert card.is_tapped
        # Untap
        untap(game, card)
        assert not card.is_tapped
