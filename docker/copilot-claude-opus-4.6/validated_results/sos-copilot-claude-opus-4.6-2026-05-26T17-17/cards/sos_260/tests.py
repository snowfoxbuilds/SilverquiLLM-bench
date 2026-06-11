"""Tests for SOS 260 — Shattered Sanctum.

Land:
- Enters tapped unless you control two or more other lands.
- {T}: Add {W} or {B}.
"""

from __future__ import annotations

from cards.sos.sos_260.card_impl import ShatteredSanctum
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestShatteredSanctumProperties:
    """Static card data should match the SOS 260 spec."""

    def test_is_land(self) -> None:
        card = ShatteredSanctum(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = ShatteredSanctum(owner=None)
        assert card.name == "Shattered Sanctum"

    def test_has_land_card_type(self) -> None:
        card = ShatteredSanctum(owner=None)
        assert CardType.LAND in card.card_types


class TestShatteredSanctumEnterCondition:
    """Enters tapped unless you control two or more other lands."""

    def test_enters_tapped_with_no_other_lands(self) -> None:
        """With 0 other lands, should enter tapped."""
        game = create_game()
        p1 = game.players[0]
        card = ShatteredSanctum(owner=p1, controller=p1)
        # No other lands on battlefield
        set_board_state(game, 0, battlefield=[])
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_tapped_with_one_other_land(self) -> None:
        """With only 1 other land, should still enter tapped."""
        game = create_game()
        p1 = game.players[0]
        other_land = Land(name="Plains", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[other_land])
        card = ShatteredSanctum(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_untapped_with_two_other_lands(self) -> None:
        """With 2+ other lands, should enter untapped."""
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Plains", owner=p1, controller=p1)
        land2 = Land(name="Swamp", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2])
        card = ShatteredSanctum(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False

    def test_enters_untapped_with_three_other_lands(self) -> None:
        """With 3 other lands, should enter untapped."""
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Plains", owner=p1, controller=p1)
        land2 = Land(name="Swamp", owner=p1, controller=p1)
        land3 = Land(name="Island", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2, land3])
        card = ShatteredSanctum(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False


class TestShatteredSanctumManaAbilities:
    """{T}: Add {W} or {B}."""

    def test_has_mana_abilities(self) -> None:
        card = ShatteredSanctum(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_white(self) -> None:
        card = ShatteredSanctum(owner=None)
        abilities = card.get_mana_abilities()
        white_found = any(
            ManaType.WHITE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert white_found is True

    def test_can_produce_black(self) -> None:
        card = ShatteredSanctum(owner=None)
        abilities = card.get_mana_abilities()
        black_found = any(
            ManaType.BLACK in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert black_found is True
