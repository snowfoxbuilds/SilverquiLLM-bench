"""Tests for SOS 265 — Terramorphic Expanse.

Land:
- {T}, Sacrifice this land: Search your library for a basic land card,
  put it onto the battlefield tapped, then shuffle.
"""

from __future__ import annotations

from cards.sos.sos_265.card_impl import TerramorphicExpanse
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestTerramorphicExpanseProperties:
    """Static card data should match the SOS 265 spec."""

    def test_is_land(self) -> None:
        card = TerramorphicExpanse(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = TerramorphicExpanse(owner=None)
        assert card.name == "Terramorphic Expanse"

    def test_has_land_card_type(self) -> None:
        card = TerramorphicExpanse(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        card = TerramorphicExpanse(owner=None)
        assert card.mana_cost is None or str(card.mana_cost) == ""


class TestTerramorphicExpanseActivatedAbility:
    """{T}, Sacrifice this land: Search library for basic land, put tapped."""

    def test_has_activated_abilities(self) -> None:
        card = TerramorphicExpanse(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_activation_sacrifices_land(self) -> None:
        """After activation, Terramorphic Expanse should no longer be on battlefield."""
        game = create_game()
        p1 = game.players[0]
        card = TerramorphicExpanse(owner=p1, controller=p1)
        basic_land = Land(name="Forest", owner=p1, controller=p1)
        basic_land.subtypes = {"Forest"}
        basic_land.supertypes = {"Basic"}
        set_board_state(game, 0, battlefield=[card], library=[basic_land])
        card.is_tapped = False
        abilities = card.get_activated_abilities()
        abilities[0].activate(game, card, p1)
        bf = game.get_battlefield(p1).get_all()
        assert card not in bf

    def test_fetched_land_enters_battlefield_tapped(self) -> None:
        """The searched basic land should enter the battlefield tapped."""
        game = create_game()
        p1 = game.players[0]
        card = TerramorphicExpanse(owner=p1, controller=p1)
        basic_land = Land(name="Forest", owner=p1, controller=p1)
        basic_land.subtypes = {"Forest"}
        basic_land.supertypes = {"Basic"}
        set_board_state(game, 0, battlefield=[card], library=[basic_land])
        card.is_tapped = False
        abilities = card.get_activated_abilities()
        abilities[0].activate(game, card, p1)
        bf = game.get_battlefield(p1).get_all()
        fetched = [c for c in bf if c.name == "Forest"]
        assert len(fetched) == 1
        assert fetched[0].is_tapped is True

    def test_no_basic_land_in_library_does_not_crash(self) -> None:
        """If library has no basic land, activation still resolves (no-op search)."""
        game = create_game()
        p1 = game.players[0]
        card = TerramorphicExpanse(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card], library=[])
        card.is_tapped = False
        abilities = card.get_activated_abilities()
        abilities[0].activate(game, card, p1)
        # Should not raise; card is sacrificed regardless
        bf = game.get_battlefield(p1).get_all()
        assert card not in bf

    def test_does_not_have_mana_abilities(self) -> None:
        """Terramorphic Expanse has no mana abilities of its own."""
        card = TerramorphicExpanse(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) == 0
