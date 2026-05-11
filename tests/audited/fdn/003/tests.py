"""Audited tests for Swamp (FDN collector number 003)."""

from __future__ import annotations

import pytest

from card_impl import Swamp

from engine.card import Land
from engine.types import ManaType, Supertype


@pytest.mark.basic
class TestSwampBasicProperties:
    def test_is_land(self) -> None:
        card = Swamp(name="Swamp", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        card = Swamp(name="Swamp", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_swamp_subtype(self) -> None:
        card = Swamp(name="Swamp", owner=None)
        assert "Swamp" in card.subtypes

    def test_name(self) -> None:
        card = Swamp(name="Swamp", owner=None)
        assert card.name == "Swamp"

    def test_enters_untapped(self) -> None:
        card = Swamp(name="Swamp", owner=None)
        assert not card.is_tapped


@pytest.mark.mana
class TestSwampManaAbility:
    def test_taps_for_black_mana(self) -> None:
        card = Swamp(name="Swamp", owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) > 0
        assert "{B}" in abilities[0].description

    def test_tapping_produces_black_mana(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        card = Swamp(name="Swamp", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        cost_paid = abilities[0].cost(game, card)
        assert cost_paid
        assert card.is_tapped
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.BLACK) >= 1

    def test_untap_after_tapping(self) -> None:
        """Swamp untaps when the untap function is called after being tapped."""
        from engine.game import untap
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        card = Swamp(name="Swamp", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert card.is_tapped
        untap(game, card)
        assert not card.is_tapped
