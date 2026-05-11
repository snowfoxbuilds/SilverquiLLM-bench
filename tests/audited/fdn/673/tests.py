"""Audited tests for Feldon's Cane (FDN collector number 673)."""
from __future__ import annotations
import pytest
from card_impl import FeldonsCane
from engine.card import Artifact, CardImpl
from engine.types import CardType, Zone
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestFeldonsCaneBasic:
    def test_is_artifact(self) -> None:
        card = FeldonsCane(name="Feldon's Cane", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = FeldonsCane(name="Feldon's Cane", owner=None)
        assert card.name == "Feldon's Cane"
    def test_has_activated_ability(self) -> None:
        card = FeldonsCane(name="Feldon's Cane", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

@pytest.mark.ability
class TestFeldonsCaneAbility:
    def test_activation_shuffles_graveyard_into_library(self) -> None:
        """Activated ability should move graveyard cards into library."""
        game = create_game()
        cane = FeldonsCane(name="Feldon's Cane", owner=game.players[0])
        cane.controller = game.players[0]
        # Put cards in graveyard
        gy_card = CardImpl(name="GraveyardCard", owner=game.players[0])
        set_board_state(game, 0, battlefield=[cane], graveyard=[gy_card])
        abilities = cane.get_activated_abilities()
        cost_paid = abilities[0].cost(game, cane)
        assert cost_paid
        abilities[0].effect(game)
        # Graveyard should be empty, library should contain the card
        gy = game.players[0].zones[Zone.GRAVEYARD]
        assert len(list(gy.get_all())) == 0

    def test_activation_taps_cane(self) -> None:
        """The cost requires tapping."""
        game = create_game()
        cane = FeldonsCane(name="Feldon's Cane", owner=game.players[0])
        cane.controller = game.players[0]
        set_board_state(game, 0, battlefield=[cane])
        abilities = cane.get_activated_abilities()
        abilities[0].cost(game, cane)
        assert cane.is_tapped

    def test_cannot_activate_when_tapped(self) -> None:
        game = create_game()
        cane = FeldonsCane(name="Feldon's Cane", owner=game.players[0])
        cane.is_tapped = True
        abilities = cane.get_activated_abilities()
        assert not abilities[0].cost(game, cane)
