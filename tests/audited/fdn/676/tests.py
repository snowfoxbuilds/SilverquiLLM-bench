"""Audited tests for Mazemind Tome (FDN collector number 676)."""
from __future__ import annotations
import pytest
from card_impl import MazemindTome
from engine.card import Artifact, CardImpl
from engine.types import CardType, Zone
from tests.test_utils import create_game, set_board_state

@pytest.mark.basic
class TestMazemindTomeBasic:
    def test_is_artifact(self) -> None:
        card = MazemindTome(name="Mazemind Tome", owner=None)
        assert isinstance(card, Artifact)
        assert CardType.ARTIFACT in card.card_types
    def test_name(self) -> None:
        card = MazemindTome(name="Mazemind Tome", owner=None)
        assert card.name == "Mazemind Tome"
    def test_starts_zero_page_counters(self) -> None:
        card = MazemindTome(name="Mazemind Tome", owner=None)
        assert card.page_counters == 0
    def test_has_two_activated_abilities(self) -> None:
        card = MazemindTome(name="Mazemind Tome", owner=None)
        assert len(card.get_activated_abilities()) == 2

@pytest.mark.ability
class TestMazemindTomeAbilities:
    def test_scry_ability_adds_page_counter(self) -> None:
        """First ability adds a page counter."""
        game = create_game()
        tome = MazemindTome(name="Mazemind Tome", owner=game.players[0])
        tome.controller = game.players[0]
        set_board_state(game, 0, battlefield=[tome])
        abilities = tome.get_activated_abilities()
        abilities[0].cost(game, tome)
        abilities[0].effect(game)
        assert tome.page_counters == 1

    def test_draw_ability_adds_page_counter_and_draws(self) -> None:
        """Second ability adds page counter and draws a card."""
        game = create_game()
        tome = MazemindTome(name="Mazemind Tome", owner=game.players[0])
        tome.controller = game.players[0]
        lib_card = CardImpl(name="LibCard", owner=game.players[0])
        set_board_state(game, 0, battlefield=[tome])
        game.players[0].zones[Zone.LIBRARY].add(lib_card)
        hand_before = len(list(game.players[0].zones[Zone.HAND].get_all()))
        abilities = tome.get_activated_abilities()
        abilities[1].cost(game, tome)
        abilities[1].effect(game)
        assert tome.page_counters == 1
        hand_after = len(list(game.players[0].zones[Zone.HAND].get_all()))
        assert hand_after == hand_before + 1

    def test_four_counters_gains_life(self) -> None:
        """At 4+ page counters, controller gains 4 life and tome is exiled."""
        game = create_game()
        tome = MazemindTome(name="Mazemind Tome", owner=game.players[0])
        tome.controller = game.players[0]
        tome.page_counters = 3  # next activation will hit 4
        set_board_state(game, 0, battlefield=[tome])
        initial_life = game.players[0].life
        abilities = tome.get_activated_abilities()
        abilities[0].cost(game, tome)
        abilities[0].effect(game)
        assert game.players[0].life == initial_life + 4
