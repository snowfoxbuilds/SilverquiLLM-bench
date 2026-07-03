"""Tests for SOS 258 — Paradox Gardens.

Land that enters tapped, taps for {G} or {U}, and has a {2}{G}{U},{T} surveil 1 ability.
"""

from __future__ import annotations

from cards.sos.sos_258.card_impl import ParadoxGardens
from engine.card import Land, ManaAbility
from engine.types import CardType, ManaType, Zone
from test_utils import create_game


class TestParadoxGardensProperties:
    """Static card data should match the SOS 258 spec."""

    def test_is_land(self) -> None:
        card = ParadoxGardens(owner=None)
        assert isinstance(card, Land)

    def test_name(self) -> None:
        card = ParadoxGardens(owner=None)
        assert card.name == "Paradox Gardens"

    def test_has_land_card_type(self) -> None:
        card = ParadoxGardens(owner=None)
        assert CardType.LAND in card.card_types

    def test_no_mana_cost(self) -> None:
        card = ParadoxGardens(owner=None)
        assert card.mana_cost is None or str(card.mana_cost) == ""


class TestParadoxGardensEntersTapped:
    """This land enters tapped."""

    def test_enters_tapped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ParadoxGardens(owner=p1, controller=p1)
        card.enter_battlefield(game)
        assert card.is_tapped is True


class TestParadoxGardensManaAbilities:
    """{T}: Add {G} or {U}."""

    def test_has_mana_abilities(self) -> None:
        card = ParadoxGardens(owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) >= 1

    def test_can_produce_green(self) -> None:
        card = ParadoxGardens(owner=None)
        abilities = card.get_mana_abilities()
        green_found = any(
            ManaType.GREEN in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert green_found is True

    def test_can_produce_blue(self) -> None:
        card = ParadoxGardens(owner=None)
        abilities = card.get_mana_abilities()
        blue_found = any(
            ManaType.BLUE in (getattr(a, 'mana_types', []) or [])
            for a in abilities
        )
        assert blue_found is True


class TestParadoxGardensSurveilAbility:
    """{2}{G}{U}, {T}: Surveil 1."""

    def test_has_activated_abilities(self) -> None:
        card = ParadoxGardens(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_surveil_puts_top_card_to_graveyard(self) -> None:
        """Surveil 1: look at top card, may put to graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = ParadoxGardens(owner=p1, controller=p1)
        from engine.card import CardImpl
        top_card = CardImpl(name="TopCard", owner=p1)
        game.get_battlefield(p1).add(card)
        card.is_tapped = False
        from test_utils import set_board_state
        set_board_state(game, 0, library=[top_card])
        abilities = card.get_activated_abilities()
        surveil_ability = abilities[0]
        surveil_ability.activate(game, card, p1, choice="graveyard")
        graveyard = game.get_graveyard(p1).get_all()
        assert any(c.name == "TopCard" for c in graveyard)
