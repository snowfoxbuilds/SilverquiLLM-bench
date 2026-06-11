"""Tests for SOS 264 — Sundown Pass.

Land:
- This land enters tapped unless you control two or more other lands.
- {T}: Add {R} or {W}.
"""

from __future__ import annotations

from cards.sos.sos_264.card_impl import SundownPass
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSundownPassProperties:
    """Static card data should match the SOS 264 spec."""

    def test_is_land(self) -> None:
        card = SundownPass(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = SundownPass(owner=None)
        assert card.name == "Sundown Pass"

    def test_has_land_card_type(self) -> None:
        card = SundownPass(owner=None)
        assert CardType.LAND in card.card_types


class TestSundownPassEnterCondition:
    """Enters tapped unless you control two or more other lands."""

    def test_enters_tapped_with_no_other_lands(self) -> None:
        """With 0 other lands, should enter tapped."""
        game = create_game()
        p1 = game.players[0]
        card = SundownPass(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_tapped_with_one_other_land(self) -> None:
        """With only 1 other land, should still enter tapped."""
        game = create_game()
        p1 = game.players[0]
        other_land = Land(name="Mountain", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[other_land])
        card = SundownPass(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_untapped_with_two_other_lands(self) -> None:
        """With 2 other lands, should enter untapped."""
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Mountain", owner=p1, controller=p1)
        land2 = Land(name="Plains", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2])
        card = SundownPass(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False

    def test_enters_untapped_with_three_other_lands(self) -> None:
        """With 3+ other lands, should enter untapped."""
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Mountain", owner=p1, controller=p1)
        land2 = Land(name="Plains", owner=p1, controller=p1)
        land3 = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2, land3])
        card = SundownPass(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False


class TestSundownPassManaAbilities:
    """{T}: Add {R} or {W}."""

    def test_has_mana_abilities(self) -> None:
        card = SundownPass(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_red(self) -> None:
        card = SundownPass(owner=None)
        abilities = card.get_mana_abilities()
        red_found = any(
            ManaType.RED in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert red_found is True

    def test_can_produce_white(self) -> None:
        card = SundownPass(owner=None)
        abilities = card.get_mana_abilities()
        white_found = any(
            ManaType.WHITE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert white_found is True
