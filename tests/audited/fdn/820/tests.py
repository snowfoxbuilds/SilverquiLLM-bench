"""Audited tests for Liliana, Dreadhorde General (FDN — synthetic dir 820)."""
from __future__ import annotations
import pytest
from card_impl import LilianaDreadhordeGeneral
from engine.card import Planeswalker, Creature
from engine.types import CardType, Supertype
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestLilianaBasic:
    def test_is_planeswalker(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert isinstance(card, Planeswalker)
    def test_starting_loyalty_is_6(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert card.loyalty == 6
    def test_is_legendary(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert Supertype.LEGENDARY in card.supertypes
    def test_has_liliana_subtype(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert "Liliana" in card.subtypes

@pytest.mark.ability
class TestLilianaAbilities:
    def test_has_three_loyalty_abilities(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert len(card.get_loyalty_abilities()) == 3
    def test_plus1_cost(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert card.get_loyalty_abilities()[0].loyalty_cost == +1
    def test_minus4_cost(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert card.get_loyalty_abilities()[1].loyalty_cost == -4
    def test_minus9_cost(self) -> None:
        card = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=None)
        assert card.get_loyalty_abilities()[2].loyalty_cost == -9
    def test_plus1_forces_opponent_sacrifice(self) -> None:
        """Liliana's +1 forces each opponent to sacrifice a creature."""
        game = create_game()
        pw = LilianaDreadhordeGeneral(name="Liliana, Dreadhorde General", owner=game.players[0])
        pw.controller = game.players[0]
        opp_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=game.players[1])
        set_board_state(game, 0, battlefield=[pw])
        set_board_state(game, 1, battlefield=[opp_creature])
        abilities = pw.get_loyalty_abilities()
        abilities[0].effect(game)
        opp_bf = game.get_battlefield(game.players[1])
        creatures = [o for o in opp_bf.get_all() if CardType.CREATURE in getattr(o, "card_types", set())]
        assert len(creatures) == 0
