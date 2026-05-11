"""Audited tests for Evolving Wilds (FDN collector number 262)."""
from __future__ import annotations
import pytest
from card_impl import EvolvingWilds
from engine.card import Land
from tests.test_utils import create_game, set_board_state


@pytest.mark.basic
class TestEvolvingWildsBasic:
    def test_is_land(self) -> None:
        card = EvolvingWilds(name="Evolving Wilds", owner=None)
        assert isinstance(card, Land)

    def test_no_mana_abilities(self) -> None:
        card = EvolvingWilds(name="Evolving Wilds", owner=None)
        assert len(card.get_mana_abilities()) == 0

    def test_has_activated_ability(self) -> None:
        card = EvolvingWilds(name="Evolving Wilds", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 1

    def test_does_not_enter_tapped(self) -> None:
        card = EvolvingWilds(name="Evolving Wilds", owner=None)
        assert not getattr(card, "enters_tapped", False)


@pytest.mark.ability
class TestEvolvingWildsAbility:
    def test_ability_description_mentions_sacrifice(self) -> None:
        card = EvolvingWilds(name="Evolving Wilds", owner=None)
        abilities = card.get_activated_abilities()
        assert "Sacrifice" in abilities[0].description

    def test_ability_description_mentions_basic_land(self) -> None:
        card = EvolvingWilds(name="Evolving Wilds", owner=None)
        abilities = card.get_activated_abilities()
        assert "basic land" in abilities[0].description

    def test_activation_taps_card(self) -> None:
        """Activating the ability taps Evolving Wilds."""
        game = create_game()
        p = game.players[0]
        card = EvolvingWilds(name="Evolving Wilds", owner=p)
        card.controller = p
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_activated_abilities()
        result = abilities[0].cost(game, card)
        assert result is True
        assert card.is_tapped

    def test_cannot_activate_when_tapped(self) -> None:
        """Cannot activate ability if already tapped."""
        game = create_game()
        p = game.players[0]
        card = EvolvingWilds(name="Evolving Wilds", owner=p)
        card.controller = p
        card.is_tapped = True
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_activated_abilities()
        result = abilities[0].cost(game, card)
        assert result is False
