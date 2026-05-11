"""Audited tests for Soul-Guide Lantern (FDN collector number 680)."""
from __future__ import annotations
import pytest
from card_impl import SoulGuideLantern
from engine.card import Artifact, CardImpl
from engine.types import CardType, Zone
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestSoulGuideLanternBasic:
    def test_is_artifact(self) -> None:
        card = SoulGuideLantern(name="Soul-Guide Lantern", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = SoulGuideLantern(name="Soul-Guide Lantern", owner=None)
        assert card.name == "Soul-Guide Lantern"
    def test_has_two_activated_abilities(self) -> None:
        card = SoulGuideLantern(name="Soul-Guide Lantern", owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) == 2

@pytest.mark.ability
class TestSoulGuideLanternAbilities:
    def test_exile_opponent_graveyard(self) -> None:
        """First ability: exile each opponent's graveyard."""
        game = create_game()
        lantern = SoulGuideLantern(name="Soul-Guide Lantern", owner=game.players[0])
        lantern.controller = game.players[0]
        # Put a card in opponent's graveyard
        opp_card = CardImpl(name="OppCard", owner=game.players[1])
        set_board_state(game, 0, battlefield=[lantern])
        set_board_state(game, 1, graveyard=[opp_card])
        abilities = lantern.get_activated_abilities()
        cost_paid = abilities[0].cost(game, lantern)
        assert cost_paid
        abilities[0].effect(game)
        # Opponent's graveyard should be empty
        opp_gy = game.players[1].zones[Zone.GRAVEYARD]
        assert len(list(opp_gy.get_all())) == 0

    def test_draw_card_ability(self) -> None:
        """Second ability: sacrifice to draw a card."""
        game = create_game()
        lantern = SoulGuideLantern(name="Soul-Guide Lantern", owner=game.players[0])
        lantern.controller = game.players[0]
        # Put a card in library
        lib_card = CardImpl(name="LibCard", owner=game.players[0])
        set_board_state(game, 0, battlefield=[lantern])
        game.players[0].zones[Zone.LIBRARY].add(lib_card)
        hand_before = len(list(game.players[0].zones[Zone.HAND].get_all()))
        abilities = lantern.get_activated_abilities()
        cost_paid = abilities[1].cost(game, lantern)
        assert cost_paid
        abilities[1].effect(game)
        hand_after = len(list(game.players[0].zones[Zone.HAND].get_all()))
        assert hand_after == hand_before + 1
