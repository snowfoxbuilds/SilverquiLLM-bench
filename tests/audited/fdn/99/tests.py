"""Audited tests for Apothecary Stomper (FDN collector number 99)."""
from __future__ import annotations
import pytest
from card_impl import ApothecaryStomper
from engine.card import Creature
from engine.types import Keyword, ManaCost


@pytest.mark.basic
class TestApothecaryStomperBasic:
    def test_is_creature(self) -> None:
        card = ApothecaryStomper()
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = ApothecaryStomper()
        assert card.name == "Apothecary Stomper"

    def test_mana_cost(self) -> None:
        card = ApothecaryStomper()
        assert card.mana_cost == ManaCost.parse("{4}{G}{G}")

    def test_power_toughness(self) -> None:
        card = ApothecaryStomper()
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_has_vigilance(self) -> None:
        card = ApothecaryStomper()
        assert Keyword.VIGILANCE & card.keywords

    def test_subtypes(self) -> None:
        card = ApothecaryStomper()
        assert "Elephant" in card.subtypes


@pytest.mark.ability
class TestApothecaryStomperModes:
    def test_has_two_modes(self) -> None:
        card = ApothecaryStomper()
        modes = card.get_modes()
        assert len(modes) == 2

    def test_mode_names(self) -> None:
        card = ApothecaryStomper()
        modes = card.get_modes()
        names = [m.name for m in modes]
        assert "Counters" in names
        assert "Life" in names

    def test_etb_life_mode_gains_four_life(self) -> None:
        """ETB mode 1 should gain 4 life."""
        from tests.test_utils import create_game, set_board_state
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = ApothecaryStomper(owner=p)
        card.controller = p
        card.chosen_mode = 1
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        life_before = p.life
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD,
                                        {"permanent": card, "controller": p})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert p.life == life_before + 4

    def test_etb_counter_mode_adds_counters(self) -> None:
        """ETB mode 0 should add two +1/+1 counters."""
        from tests.test_utils import create_game, set_board_state
        from engine.triggers import EventType
        game = create_game()
        p = game.players[0]
        card = ApothecaryStomper(owner=p)
        card.controller = p
        card.chosen_mode = 0
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        counters_before = card.plus_one_counters
        game.trigger_manager.fire_event(game, EventType.ENTERS_BATTLEFIELD,
                                        {"permanent": card, "controller": p})
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)
        assert card.plus_one_counters == counters_before + 2
