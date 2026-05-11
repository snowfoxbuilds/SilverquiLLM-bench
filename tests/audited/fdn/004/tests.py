"""Audited tests for Mountain (FDN collector number 004)."""

from __future__ import annotations

import pytest

from card_impl import Mountain

from engine.card import Land
from engine.types import ManaType, Supertype


@pytest.mark.basic
class TestMountainBasicProperties:
    def test_is_land(self) -> None:
        card = Mountain(name="Mountain", owner=None)
        assert isinstance(card, Land)

    def test_has_basic_supertype(self) -> None:
        card = Mountain(name="Mountain", owner=None)
        assert Supertype.BASIC in card.supertypes

    def test_has_mountain_subtype(self) -> None:
        card = Mountain(name="Mountain", owner=None)
        assert "Mountain" in card.subtypes

    def test_name(self) -> None:
        card = Mountain(name="Mountain", owner=None)
        assert card.name == "Mountain"

    def test_enters_untapped(self) -> None:
        card = Mountain(name="Mountain", owner=None)
        assert not card.is_tapped


@pytest.mark.mana
class TestMountainManaAbility:
    def test_taps_for_red_mana(self) -> None:
        card = Mountain(name="Mountain", owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) > 0
        assert "{R}" in abilities[0].description

    def test_tapping_produces_red_mana(self) -> None:
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        card = Mountain(name="Mountain", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        cost_paid = abilities[0].cost(game, card)
        assert cost_paid
        assert card.is_tapped
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.RED) >= 1

    def test_untap_after_tapping(self) -> None:
        """Mountain untaps when the untap function is called after being tapped."""
        from engine.game import untap
        from tests.test_utils import create_game, set_board_state

        game = create_game()
        card = Mountain(name="Mountain", owner=game.players[0])
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        assert card.is_tapped
        untap(game, card)
        assert not card.is_tapped
