"""Tests for SOS 176 — Blech, Loafing Pest."""

from __future__ import annotations

import pytest

from cards.sos.sos_176.card_impl import BlechLoafingPest
from engine.card import Creature
from engine.types import ManaCost, ManaType, Keyword
from test_utils import create_game, set_board_state


class TestBlechLoafingPestProperties:
    """Static card properties match spec."""

    def test_is_creature(self) -> None:
        card = BlechLoafingPest(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert BlechLoafingPest(owner=None).name == "Blech, Loafing Pest"

    def test_mana_cost(self) -> None:
        assert BlechLoafingPest(owner=None).mana_cost == ManaCost.parse("{1}{B}{G}")

    def test_power_toughness(self) -> None:
        card = BlechLoafingPest(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 4

    def test_legendary(self) -> None:
        card = BlechLoafingPest(owner=None)
        assert card.legendary is True


class TestBlechLoafingPestTrigger:
    """Whenever you gain life, put a +1/+1 counter on each Pest, Bat, Insect, Snake, Spider."""

    def test_gain_life_puts_counter_on_pest(self) -> None:
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        pest = Creature(name="Token Pest", base_power=1, base_toughness=1)
        pest.creature_types = {"Pest"}
        pest.owner = game.players[0]
        set_board_state(game, 0, battlefield=[blech, pest])
        # Simulate gaining life
        game.players[0].gain_life(1)
        # After trigger resolves, pest should have a +1/+1 counter
        assert pest.counters.get("+1/+1", 0) >= 1

    def test_gain_life_puts_counter_on_bat(self) -> None:
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        bat = Creature(name="Token Bat", base_power=1, base_toughness=1)
        bat.creature_types = {"Bat"}
        bat.owner = game.players[0]
        set_board_state(game, 0, battlefield=[blech, bat])
        game.players[0].gain_life(2)
        assert bat.counters.get("+1/+1", 0) >= 1

    def test_gain_life_puts_counter_on_insect(self) -> None:
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        insect = Creature(name="Token Insect", base_power=1, base_toughness=1)
        insect.creature_types = {"Insect"}
        insect.owner = game.players[0]
        set_board_state(game, 0, battlefield=[blech, insect])
        game.players[0].gain_life(1)
        assert insect.counters.get("+1/+1", 0) >= 1

    def test_gain_life_puts_counter_on_snake(self) -> None:
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        snake = Creature(name="Token Snake", base_power=1, base_toughness=1)
        snake.creature_types = {"Snake"}
        snake.owner = game.players[0]
        set_board_state(game, 0, battlefield=[blech, snake])
        game.players[0].gain_life(1)
        assert snake.counters.get("+1/+1", 0) >= 1

    def test_gain_life_puts_counter_on_spider(self) -> None:
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        spider = Creature(name="Token Spider", base_power=2, base_toughness=4)
        spider.creature_types = {"Spider"}
        spider.owner = game.players[0]
        set_board_state(game, 0, battlefield=[blech, spider])
        game.players[0].gain_life(1)
        assert spider.counters.get("+1/+1", 0) >= 1

    def test_non_qualifying_creature_does_not_get_counter(self) -> None:
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2)
        bear.creature_types = {"Bear"}
        bear.owner = game.players[0]
        set_board_state(game, 0, battlefield=[blech, bear])
        game.players[0].gain_life(1)
        assert bear.counters.get("+1/+1", 0) == 0

    def test_blech_itself_gets_counter_as_pest(self) -> None:
        """Blech is a Pest, so it should get a counter too."""
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        set_board_state(game, 0, battlefield=[blech])
        game.players[0].gain_life(1)
        assert blech.counters.get("+1/+1", 0) >= 1

    def test_opponent_gain_life_does_not_trigger(self) -> None:
        game = create_game()
        blech = BlechLoafingPest(owner=game.players[0])
        pest = Creature(name="Token Pest", base_power=1, base_toughness=1)
        pest.creature_types = {"Pest"}
        pest.owner = game.players[0]
        set_board_state(game, 0, battlefield=[blech, pest])
        # Opponent gains life — should NOT trigger
        game.players[1].gain_life(3)
        assert pest.counters.get("+1/+1", 0) == 0
