"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import Any

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import AbilityError, ActivateAbility
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _stock_library(game: Any, player_index: int, cards_top_first: list[Any]) -> None:
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in reversed(cards_top_first):
        card.owner = player
        card.controller = player
        library.add(card)


def _setup(game: Any) -> Any:
    """Put Ral on p1's battlefield at sorcery speed for p1."""
    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    return ral


class TestProperties:
    def test_static_data(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert CardType.PLANESWALKER in card.card_types
        assert Supertype.LEGENDARY in card.supertypes


class TestPlusOneSurveil:
    def test_surveil_two_bins_and_keeps(self) -> None:
        game = create_game(scripts=(["pass", True, False], ["pass"]))
        p1 = game.players[0]
        ral = _setup(game)
        a = Creature(name="Top Card", base_power=1, base_toughness=1)
        b = Creature(name="Second Card", base_power=1, base_toughness=1)
        c = Creature(name="Deep Card", base_power=1, base_toughness=1)
        _stock_library(game, 0, [a, b, c])
        ActivateAbility(game, p1, ral, 0)
        priority_loop(game)
        assert p1.zones[Zone.GRAVEYARD].contains(a)
        assert p1.zones[Zone.LIBRARY].top(1)[0] is b
        assert ral.loyalty == 4


class TestMinusOneDiscard:
    def test_each_target_player_discards(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1, p2 = game.players
        ral = _setup(game)
        h1 = Creature(name="P1 Card", base_power=1, base_toughness=1)
        h2 = Creature(name="P2 Card", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[h1])
        set_board_state(game, 1, hand=[h2])
        p1._script.append(h1)
        p2._script.append(h2)
        ActivateAbility(game, p1, ral, 1, targets=[p1, p2])
        priority_loop(game)
        assert p1.zones[Zone.GRAVEYARD].contains(h1)
        assert p2.zones[Zone.GRAVEYARD].contains(h2)
        assert ral.loyalty == 2

    def test_zero_targets_is_legal_noop(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        ral = _setup(game)
        ActivateAbility(game, p1, ral, 1, targets=[])
        priority_loop(game)
        assert ral.loyalty == 2


class TestMinusTwoReanimate:
    def test_returns_cheap_creature_from_graveyard(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        ral = _setup(game)
        bear = Creature(name="Bear", mana_cost=ManaCost(generic=3),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])
        ActivateAbility(game, p1, ral, 2, targets=[bear])
        priority_loop(game)
        assert game.get_battlefield(p1).contains(bear)
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)
        assert ral.loyalty == 1

    def test_mana_value_above_three_is_not_returned(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        ral = _setup(game)
        giant = Creature(name="Giant", mana_cost=ManaCost(generic=4),
                         base_power=4, base_toughness=4)
        set_board_state(game, 0, graveyard=[giant])
        ActivateAbility(game, p1, ral, 2, targets=[giant])
        priority_loop(game)
        assert p1.zones[Zone.GRAVEYARD].contains(giant)
        assert not game.get_battlefield(p1).contains(giant)


class TestMinusSevenUltimate:
    def test_requires_seven_loyalty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = _setup(game)  # loyalty 3
        with pytest.raises(AbilityError):
            ActivateAbility(game, p1, ral, 3, targets=[p2])
        assert ral.loyalty == 3

    def test_heads_make_opponent_skip_turns(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1, p2 = game.players
        ral = _setup(game)
        ral.loyalty = 7
        seed = 4
        rng = random.Random(seed)
        expected_heads = sum(rng.randint(0, 1) for _ in range(5))
        assert expected_heads > 0  # seed chosen for a non-zero ultimate
        game.rng = random.Random(seed)
        ActivateAbility(game, p1, ral, 3, targets=[p2])
        priority_loop(game)
        assert ral.loyalty == 0
        assert getattr(p2, "skip_turns", 0) == expected_heads
        # The skipped player never becomes active until the count drains.
        for _ in range(expected_heads):
            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            game.advance_phase()  # wrap into a new turn
            assert game.active_player is p1
        assert getattr(p2, "skip_turns", 0) == 0
        # After the counter drains, p2 finally takes a turn.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()
        assert game.active_player is p2

    def test_zero_heads_skips_nothing(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1, p2 = game.players
        ral = _setup(game)
        ral.loyalty = 7
        seed = 15
        rng = random.Random(seed)
        expected_heads = sum(rng.randint(0, 1) for _ in range(5))
        assert expected_heads == 0  # seed chosen for an all-tails flip
        game.rng = random.Random(seed)
        ActivateAbility(game, p1, ral, 3, targets=[p2])
        priority_loop(game)
        assert getattr(p2, "skip_turns", 0) == 0
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()
        assert game.active_player is p2  # takes their turn normally


class TestOncePerTurn:
    def test_second_loyalty_activation_same_turn_fails(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        ral = _setup(game)
        _stock_library(game, 0, [])
        ActivateAbility(game, p1, ral, 0)
        priority_loop(game)  # surveil with empty library — no prompts
        with pytest.raises(AbilityError):
            ActivateAbility(game, p1, ral, 1, targets=[])
