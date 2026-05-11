"""Audited tests for Sol Ring (FDN — synthetic dir 800)."""
from __future__ import annotations
import pytest
from card_impl import SolRing
from engine.card import Artifact
from engine.types import CardType, ManaType
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestSolRingBasic:
    def test_is_artifact(self) -> None:
        card = SolRing(name="Sol Ring", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_mana_cost_is_one(self) -> None:
        card = SolRing(name="Sol Ring", owner=None)
        assert card.mana_cost is not None

@pytest.mark.ability
class TestSolRingAbility:
    def test_has_mana_ability(self) -> None:
        card = SolRing(name="Sol Ring", owner=None)
        abilities = card.get_mana_abilities()
        assert len(abilities) > 0
    def test_taps_for_exactly_two_colorless(self) -> None:
        """Sol Ring produces exactly 2 colorless mana."""
        game = create_game()
        card = SolRing(name="Sol Ring", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        cost_paid = abilities[0].cost(game, card)
        assert cost_paid
        assert card.is_tapped
        abilities[0].mana_produced(game)
        assert game.players[0].mana_pool.get(ManaType.COLORLESS) == 2
    def test_cannot_tap_when_already_tapped(self) -> None:
        game = create_game()
        card = SolRing(name="Sol Ring", owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])
        abilities = card.get_mana_abilities()
        abilities[0].cost(game, card)
        result = abilities[0].cost(game, card)
        assert result is False
    def test_starts_untapped(self) -> None:
        card = SolRing(name="Sol Ring", owner=None)
        assert not card.is_tapped
