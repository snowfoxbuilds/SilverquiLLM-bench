"""Audited tests for Kaito, Cunning Infiltrator (FDN collector number 44)."""
from __future__ import annotations
import pytest
from card_impl import KaitoCunningInfiltrator
from engine.card import Planeswalker, Creature
from engine.types import CardType, Supertype, Zone
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestKaitoBasic:
    def test_is_planeswalker(self) -> None:
        card = KaitoCunningInfiltrator(name="Kaito, Cunning Infiltrator", owner=None)
        assert isinstance(card, Planeswalker)
    def test_starting_loyalty(self) -> None:
        card = KaitoCunningInfiltrator(name="Kaito, Cunning Infiltrator", owner=None)
        assert card.loyalty == 3
    def test_is_legendary(self) -> None:
        card = KaitoCunningInfiltrator(name="Kaito, Cunning Infiltrator", owner=None)
        assert Supertype.LEGENDARY in card.supertypes

@pytest.mark.ability
class TestKaitoAbilities:
    def test_has_three_loyalty_abilities(self) -> None:
        card = KaitoCunningInfiltrator(name="Kaito, Cunning Infiltrator", owner=None)
        assert len(card.get_loyalty_abilities()) == 3
    def test_plus1_cost(self) -> None:
        card = KaitoCunningInfiltrator(name="Kaito, Cunning Infiltrator", owner=None)
        assert card.get_loyalty_abilities()[0].loyalty_cost == +1
    def test_minus2_creates_token(self) -> None:
        game = create_game()
        pw = KaitoCunningInfiltrator(name="Kaito, Cunning Infiltrator", owner=game.players[0])
        pw.controller = game.players[0]
        set_board_state(game, 0, battlefield=[pw])
        abilities = pw.get_loyalty_abilities()
        abilities[1].effect(game)  # -2: Create Ninja token
        bf = game.get_battlefield(game.players[0])
        tokens = [c for c in bf.get_all() if getattr(c, "name", "") == "Ninja"]
        assert len(tokens) == 1
        assert tokens[0].base_power == 2
        assert tokens[0].base_toughness == 1
