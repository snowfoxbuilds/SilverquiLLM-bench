"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker)."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


@pytest.fixture(autouse=True)
def _reset_loyalty_tracker() -> Any:
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _ral(player: Any) -> RalZarekGuestLecturer:
    return RalZarekGuestLecturer(owner=player, controller=player)


def _creature(player: Any, name: str = "Bear", cmc: int = 2) -> Creature:
    return Creature(
        name=name,
        owner=player,
        controller=player,
        mana_cost=ManaCost(generic=cmc),
        base_power=2,
        base_toughness=2,
    )


def _set_library(player: Any, cards: list[Any]) -> None:
    """Replace a player's library; the last item is the top card."""
    library = player.zones[Zone.LIBRARY]
    for obj in library.get_all():
        library.remove(obj)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _resolve_stack(game: Any) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _setup_sorcery_speed(game: Any, ral: RalZarekGuestLecturer) -> None:
    """Place Ral on the battlefield and arrange sorcery-speed timing for p1."""
    set_board_state(game, 0, battlefield=[ral])
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _activate(game: Any, player: Any, ral: RalZarekGuestLecturer, index: int) -> None:
    ability = ral.get_loyalty_abilities()[index]
    instance = LoyaltyAbilityInstance(
        source=ral,
        controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
    )
    activate_ability(game, player, instance)
    _resolve_stack(game)


class TestRalProperties:
    def test_name(self) -> None:
        assert RalZarekGuestLecturer().name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer().mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker(self) -> None:
        assert CardType.PLANESWALKER in RalZarekGuestLecturer().card_types

    def test_starting_loyalty(self) -> None:
        ral = RalZarekGuestLecturer()
        assert ral.starting_loyalty == 3
        assert ral.loyalty == 3

    def test_legendary_and_subtype(self) -> None:
        ral = RalZarekGuestLecturer()
        assert Supertype.LEGENDARY in ral.supertypes
        assert "Ral" in ral.subtypes

    def test_colors(self) -> None:
        assert RalZarekGuestLecturer().colors == ["B"]

    def test_loyalty_ability_costs(self) -> None:
        costs = [a.loyalty_cost for a in RalZarekGuestLecturer().get_loyalty_abilities()]
        assert costs == [1, -1, -2, -7]


class TestPlusOneSurveil:
    def test_surveil_puts_chosen_card_in_graveyard(self) -> None:
        # Look at top two; bury the top card, keep the second.
        game = create_game(scripts=([True, False], []))
        p1, _ = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        deep = _creature(p1, "Deep")
        b = _creature(p1, "B")
        a = _creature(p1, "A")
        _set_library(p1, [deep, b, a])  # 'a' is on top

        _activate(game, p1, ral, 0)

        assert ral.loyalty == 4  # +1
        assert p1.zones[Zone.GRAVEYARD].contains(a)
        assert p1.zones[Zone.LIBRARY].contains(b)
        assert p1.zones[Zone.LIBRARY].contains(deep)

    def test_surveil_can_keep_everything(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1, _ = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        b = _creature(p1, "B")
        a = _creature(p1, "A")
        _set_library(p1, [b, a])

        _activate(game, p1, ral, 0)

        assert len(p1.zones[Zone.GRAVEYARD]) == 0
        assert p1.zones[Zone.LIBRARY].contains(a)
        assert p1.zones[Zone.LIBRARY].contains(b)

    def test_surveil_handles_thin_library(self) -> None:
        game = create_game(scripts=([True], []))
        p1, _ = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        only = _creature(p1, "Only")
        _set_library(p1, [only])

        _activate(game, p1, ral, 0)  # must not raise on a 1-card library

        assert p1.zones[Zone.GRAVEYARD].contains(only)


class TestMinusOneDiscard:
    def test_targets_only_opponent(self) -> None:
        # p1 declines to target self, targets p2; p2 discards its card.
        game = create_game(scripts=([False, True], []))
        p1, p2 = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        p1_card = _creature(p1, "Keep")
        p2_card = _creature(p2, "Lose")
        set_board_state(game, 0, battlefield=[ral], hand=[p1_card])
        set_board_state(game, 1, hand=[p2_card])
        p2._script.append(p2_card)  # p2 chooses what to discard

        _activate(game, p1, ral, 1)

        assert ral.loyalty == 2  # -1
        assert p2.zones[Zone.GRAVEYARD].contains(p2_card)
        assert p1.zones[Zone.HAND].contains(p1_card)

    def test_targets_nobody(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1, p2 = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        p2_card = _creature(p2, "Safe")
        set_board_state(game, 1, hand=[p2_card])

        _activate(game, p1, ral, 1)

        assert p2.zones[Zone.HAND].contains(p2_card)
        assert len(p2.zones[Zone.GRAVEYARD]) == 0


class TestMinusTwoReanimate:
    def test_returns_small_creature_to_battlefield(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        bear = _creature(p1, "Bear", cmc=2)
        set_board_state(game, 0, battlefield=[ral], graveyard=[bear])
        p1._script.append(bear)  # choose the bear to reanimate

        _activate(game, p1, ral, 2)

        assert ral.loyalty == 1  # -2
        assert game.get_battlefield(p1).contains(bear)
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_ignores_creatures_with_high_mana_value(self) -> None:
        game = create_game(scripts=([], []))
        p1, _ = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        big = _creature(p1, "Big", cmc=5)  # MV 5 > 3 — not a legal target
        set_board_state(game, 0, battlefield=[ral], graveyard=[big])

        # No valid candidate → no choice is requested and nothing moves.
        _activate(game, p1, ral, 2)

        assert p1.zones[Zone.GRAVEYARD].contains(big)
        assert not game.get_battlefield(p1).contains(big)


class TestMinusSevenCoinFlips:
    def test_heads_set_opponent_skip_count(self) -> None:
        # Three heads out of five.
        game = create_game(scripts=([True, True, True, False, False], []))
        p1, p2 = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        ral.loyalty = 7  # afford the ultimate

        _activate(game, p1, ral, 3)

        assert ral.loyalty == 0
        assert p2.skipped_turns == 3

    def test_all_tails_skips_nothing(self) -> None:
        game = create_game(scripts=([False, False, False, False, False], []))
        p1, p2 = game.players
        ral = _ral(p1)
        _setup_sorcery_speed(game, ral)
        ral.loyalty = 7

        _activate(game, p1, ral, 3)

        assert p2.skipped_turns == 0


class TestSkippedTurnIntegration:
    def test_skipped_turn_is_passed_over(self) -> None:
        from engine.turn import run_turn

        game = create_game(scripts=([], []))
        p1, p2 = game.players
        p2.skipped_turns = 1

        run_turn(game)  # p1's turn 1 → advances to p2's turn 2
        assert game.active_player is p2
        assert game.turn_number == 2

        run_turn(game)  # p2's turn is skipped, consuming the counter
        assert p2.skipped_turns == 0
        assert game.active_player is p1
        assert game.turn_number == 3
