"""Audited tests for Nissa, Worldwaker (FDN — synthetic dir 821)."""
from __future__ import annotations
import pytest
from card_impl import NissaWorldwaker
from engine.card import Planeswalker, Land
from engine.types import CardType, Supertype
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestNissaBasic:
    def test_is_planeswalker(self) -> None:
        card = NissaWorldwaker(name="Nissa, Worldwaker", owner=None)
        assert isinstance(card, Planeswalker)
    def test_starting_loyalty_is_3(self) -> None:
        card = NissaWorldwaker(name="Nissa, Worldwaker", owner=None)
        assert card.loyalty == 3
    def test_is_legendary(self) -> None:
        card = NissaWorldwaker(name="Nissa, Worldwaker", owner=None)
        assert Supertype.LEGENDARY in card.supertypes
    def test_has_nissa_subtype(self) -> None:
        card = NissaWorldwaker(name="Nissa, Worldwaker", owner=None)
        assert "Nissa" in card.subtypes

@pytest.mark.ability
class TestNissaAbilities:
    def test_has_three_loyalty_abilities(self) -> None:
        card = NissaWorldwaker(name="Nissa, Worldwaker", owner=None)
        assert len(card.get_loyalty_abilities()) == 3
    def test_two_plus1_abilities(self) -> None:
        card = NissaWorldwaker(name="Nissa, Worldwaker", owner=None)
        abilities = card.get_loyalty_abilities()
        plus1_count = sum(1 for a in abilities if a.loyalty_cost == +1)
        assert plus1_count == 2
    def test_minus7_cost(self) -> None:
        card = NissaWorldwaker(name="Nissa, Worldwaker", owner=None)
        assert card.get_loyalty_abilities()[2].loyalty_cost == -7
    def test_plus1_animate_sets_power_toughness(self) -> None:
        """Nissa's first +1 animates a land as a 4/4."""
        game = create_game()
        pw = NissaWorldwaker(name="Nissa, Worldwaker", owner=game.players[0])
        pw.controller = game.players[0]
        land = Land(name="Forest", owner=game.players[0])
        land.base_power = 0
        land.base_toughness = 0
        set_board_state(game, 0, battlefield=[pw, land])
        pw._resolve_target = land
        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)
        assert land.base_power == 4
        assert land.base_toughness == 4
