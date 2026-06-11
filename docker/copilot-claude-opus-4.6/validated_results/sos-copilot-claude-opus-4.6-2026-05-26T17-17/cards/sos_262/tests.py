"""Tests for SOS 262 — Spectacle Summit.

Land:
- This land enters tapped.
- {T}: Add {U} or {R}.
- {2}{U}{R}, {T}: Surveil 1.
"""

from __future__ import annotations

from cards.sos.sos_262.card_impl import SpectacleSummit
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game, set_board_state


class TestSpectacleSummitProperties:
    """Static card data should match the SOS 262 spec."""

    def test_is_land(self) -> None:
        card = SpectacleSummit(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = SpectacleSummit(owner=None)
        assert card.name == "Spectacle Summit"

    def test_has_land_card_type(self) -> None:
        card = SpectacleSummit(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        card = SpectacleSummit(owner=None)
        assert card.mana_cost is None or str(card.mana_cost) == ""


class TestSpectacleSummitEntersTapped:
    """This land enters tapped."""

    def test_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpectacleSummit(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True

    def test_enters_tapped_even_with_many_lands(self) -> None:
        """Always enters tapped regardless of board state."""
        game = create_game()
        p1 = game.players[0]
        land1 = Land(name="Island", owner=p1, controller=p1)
        land2 = Land(name="Mountain", owner=p1, controller=p1)
        land3 = Land(name="Forest", owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[land1, land2, land3])
        card = SpectacleSummit(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True


class TestSpectacleSummitManaAbilities:
    """{T}: Add {U} or {R}."""

    def test_has_mana_abilities(self) -> None:
        card = SpectacleSummit(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_blue(self) -> None:
        card = SpectacleSummit(owner=None)
        abilities = card.get_mana_abilities()
        blue_found = any(
            ManaType.BLUE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert blue_found is True

    def test_can_produce_red(self) -> None:
        card = SpectacleSummit(owner=None)
        abilities = card.get_mana_abilities()
        red_found = any(
            ManaType.RED in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert red_found is True


class TestSpectacleSummitSurveilAbility:
    """{2}{U}{R}, {T}: Surveil 1."""

    def test_has_activated_abilities(self) -> None:
        card = SpectacleSummit(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_surveil_puts_top_card_to_graveyard(self) -> None:
        """Surveil 1: look at top card, may put to graveyard."""
        from engine.card import CardImpl
        game = create_game()
        p1 = game.players[0]
        card = SpectacleSummit(owner=p1, controller=p1)
        top_card = CardImpl(name="TopCard", owner=p1)
        game.get_battlefield(p1).add(card)
        card.is_tapped = False
        set_board_state(game, 0, library=[top_card])
        abilities = card.get_activated_abilities()
        surveil_ability = abilities[0]
        surveil_ability.activate(game, card, p1, choice="graveyard")
        graveyard = game.get_graveyard(p1).get_all()
        assert any(c.name == "TopCard" for c in graveyard)
