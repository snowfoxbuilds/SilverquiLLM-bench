"""Tests for SOS 263 — Stormcarved Coast.

Land:
- This land enters tapped unless you control two or more other lands.
- {T}: Add {U} or {R}.
"""

from __future__ import annotations

from cards.sos.sos_263.card_impl import StormcarvedCoast
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestStormcarvedCoastProperties:
    """Static card data should match the SOS 263 spec."""

    def test_is_land(self) -> None:
        card = StormcarvedCoast(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = StormcarvedCoast(owner=None)
        assert card.name == "Stormcarved Coast"

    def test_has_land_card_type(self) -> None:
        card = StormcarvedCoast(owner=None)
        assert CardType.LAND in card.card_types


class TestStormcarvedCoastEnterCondition:
    """Enters tapped unless you control two or more other lands."""

    def test_enters_tapped_with_no_other_lands(self) -> None:
        """With 0 other lands, should enter tapped."""
        game = create_game()
        p1 = game.players[0]
        card = StormcarvedCoast(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[])
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_tapped_with_one_other_land(self) -> None:
        """With only 1 other land, should still enter tapped."""
        game = create_game()
        p1 = game.players[0]
        other_land = Land(name="Island", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[other_land])
        card = StormcarvedCoast(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_untapped_with_two_other_lands(self) -> None:
        """With 2 other lands, should enter untapped."""
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Island", owner=p1, controller=p1)
        land2 = Land(name="Mountain", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2])
        card = StormcarvedCoast(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False

    def test_enters_untapped_with_three_other_lands(self) -> None:
        """With 3+ other lands, should enter untapped."""
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Island", owner=p1, controller=p1)
        land2 = Land(name="Mountain", owner=p1, controller=p1)
        land3 = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2, land3])
        card = StormcarvedCoast(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is False


class TestStormcarvedCoastManaAbilities:
    """{T}: Add {U} or {R}."""

    def test_has_mana_abilities(self) -> None:
        card = StormcarvedCoast(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_blue(self) -> None:
        card = StormcarvedCoast(owner=None)
        abilities = card.get_mana_abilities()
        blue_found = any(
            ManaType.BLUE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert blue_found is True

    def test_can_produce_red(self) -> None:
        card = StormcarvedCoast(owner=None)
        abilities = card.get_mana_abilities()
        red_found = any(
            ManaType.RED in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert red_found is True
