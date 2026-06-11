"""Tests for SOS 255 — Fields of Strife.

Land:
- This land enters tapped.
- {T}: Add {R} or {W}.
- {2}{R}{W}, {T}: Surveil 1.
"""

from __future__ import annotations

from cards.sos.sos_255.card_impl import FieldsOfStrife
from engine.card import Land, ManaAbility, ActivatedAbility
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game


class TestFieldsOfStrifeProperties:
    """Static card data should match the SOS 255 spec."""

    def test_name(self) -> None:
        card = FieldsOfStrife(owner=None)
        assert card.name == "Fields of Strife"

    def test_is_land(self) -> None:
        card = FieldsOfStrife(owner=None)
        assert isinstance(card, Land)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        card = FieldsOfStrife(owner=None)
        assert card.mana_cost is None or card.mana_cost == ManaCost.parse("{0}")


class TestFieldsOfStrifeManaAbilities:
    """{T}: Add {R} or {W}."""

    def test_has_mana_abilities(self) -> None:
        card = FieldsOfStrife(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_red(self) -> None:
        card = FieldsOfStrife(owner=None)
        abilities = card.get_mana_abilities()
        all_types = []
        for a in abilities:
            if hasattr(a, "mana_types"):
                all_types.extend(a.mana_types)
            elif hasattr(a, "mana_type"):
                all_types.append(a.mana_type)
        assert ManaType.RED in all_types

    def test_can_produce_white(self) -> None:
        card = FieldsOfStrife(owner=None)
        abilities = card.get_mana_abilities()
        all_types = []
        for a in abilities:
            if hasattr(a, "mana_types"):
                all_types.extend(a.mana_types)
            elif hasattr(a, "mana_type"):
                all_types.append(a.mana_type)
        assert ManaType.WHITE in all_types


class TestFieldsOfStrifeEntersTapped:
    """This land always enters tapped."""

    def test_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = FieldsOfStrife(owner=p1, controller=p1)
        card.on_enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_tapped_even_with_many_lands(self) -> None:
        """Unlike conditional lands, this always enters tapped."""
        game = create_game()
        p1 = game.players[0]
        for i in range(5):
            land = Land(owner=p1, controller=p1, name=f"Land{i}")
            game.get_battlefield(p1).add(land)
        card = FieldsOfStrife(owner=p1, controller=p1)
        card.on_enter_battlefield(game)
        assert card.is_tapped is True


class TestFieldsOfStrifeSurveilAbility:
    """{2}{R}{W}, {T}: Surveil 1."""

    def test_has_surveil_activated_ability(self) -> None:
        card = FieldsOfStrife(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_surveil_puts_top_card_in_graveyard(self) -> None:
        """Surveil 1: look at top card, may put into graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = FieldsOfStrife(owner=p1, controller=p1)
        card.is_tapped = False
        # Put a card on top of library
        from engine.card import CardImpl
        top_card = CardImpl(owner=p1, controller=p1, name="TopCard")
        p1.zones[Zone.LIBRARY].add(top_card)
        abilities = card.get_activated_abilities()
        surveil_ability = abilities[0]
        # Activate with choice to put into graveyard
        surveil_ability.activate(game, card, p1, surveil_choice="graveyard")
        graveyard_cards = p1.zones[Zone.GRAVEYARD].get_all()
        assert any(c.name == "TopCard" for c in graveyard_cards)

    def test_surveil_keeps_top_card_on_library(self) -> None:
        """Surveil 1: look at top card, may keep on top of library."""
        game = create_game()
        p1 = game.players[0]
        card = FieldsOfStrife(owner=p1, controller=p1)
        card.is_tapped = False
        from engine.card import CardImpl
        top_card = CardImpl(owner=p1, controller=p1, name="TopCard")
        p1.zones[Zone.LIBRARY].add(top_card)
        abilities = card.get_activated_abilities()
        surveil_ability = abilities[0]
        # Activate with choice to keep on top
        surveil_ability.activate(game, card, p1, surveil_choice="library")
        library_cards = p1.zones[Zone.LIBRARY].get_all()
        assert any(c.name == "TopCard" for c in library_cards)

    def test_surveil_taps_the_land(self) -> None:
        """Activating the surveil ability should tap the land."""
        game = create_game()
        p1 = game.players[0]
        card = FieldsOfStrife(owner=p1, controller=p1)
        card.is_tapped = False
        from engine.card import CardImpl
        top_card = CardImpl(owner=p1, controller=p1, name="TopCard")
        p1.zones[Zone.LIBRARY].add(top_card)
        abilities = card.get_activated_abilities()
        surveil_ability = abilities[0]
        surveil_ability.activate(game, card, p1)
        assert card.is_tapped is True
