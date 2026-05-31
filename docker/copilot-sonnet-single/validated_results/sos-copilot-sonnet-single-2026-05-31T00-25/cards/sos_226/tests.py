"""Tests for sos_226 — Silverquill, the Disputant."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype
from test_utils import create_game, set_board_state


class TestSilverquillTheDisputantProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_base_power(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4

    def test_base_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_toughness == 4

    def test_is_creature(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types

    def test_has_flying(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_has_vigilance(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.VIGILANCE in card.keywords

    def test_is_legendary(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtypes_include_elder_dragon(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes


class TestSilverquillCasualtyGranting:
    """Silverquill should grant casualty 1 to instants/sorceries."""

    def test_grants_casualty_flag_is_set(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.grants_casualty_to_instants_and_sorceries is True

    def test_casualty_value_is_one(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.casualty_value == 1

    def test_casualty_flag_readable_from_battlefield(self) -> None:
        """When on the battlefield, the casualty flag is accessible."""
        game = create_game()
        p1 = game.players[0]
        card = SilverquillTheDisputant(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])

        bf = game.get_battlefield(p1)
        for obj in bf.get_all():
            if obj is card:
                assert getattr(obj, "grants_casualty_to_instants_and_sorceries", False) is True
                assert getattr(obj, "casualty_value", 0) == 1
