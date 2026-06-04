"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker)."""

from __future__ import annotations

from typing import Any

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _creature(name: str, cost: str) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse(cost),
        base_power=2,
        base_toughness=2,
    )


def _setup_sorcery_speed(game: Any) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _drain(game: Any) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestRalProperties:
    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_cost(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert c.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_loyalty(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert c.starting_loyalty == 3 and c.loyalty == 3

    def test_legendary_ral_planeswalker(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert "Ral" in c.subtypes
        assert CardType.PLANESWALKER in c.card_types

    def test_four_abilities(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in c.get_loyalty_abilities()]
        assert costs == [1, -1, -2, -7]


class TestRalSurveil:
    def test_plus1_surveil_2(self) -> None:
        # First top card → graveyard, second → kept on top.
        game = create_game(scripts=([True, False], []))
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        a = _creature("A", "{1}")
        b = _creature("B", "{1}")
        lib = p1.zones[Zone.LIBRARY]
        lib.add(a)  # bottom of the two
        lib.add(b)  # top, examined first
        ral.get_loyalty_abilities()[0].effect(game)
        assert game.get_graveyard(p1).contains(b)
        assert lib.contains(a)


class TestRalDiscard:
    def test_minus1_targets_opponent(self) -> None:
        card = _creature("Discardable", "{1}")
        game = create_game(scripts=([False, True], [card]))
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 1, hand=[card])
        ral.get_loyalty_abilities()[1].effect(game)
        assert game.get_graveyard(p2).contains(card)
        assert not game.get_hand(p2).contains(card)


class TestRalReanimate:
    def test_minus2_returns_low_cmc_creature(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        small = _creature("Small", "{1}{B}")     # cmc 2 — eligible
        big = _creature("Big", "{4}{B}{B}")       # cmc 6 — ineligible
        set_board_state(game, 0, graveyard=[small, big])
        ral._resolve_target = small
        ral.get_loyalty_abilities()[2].effect(game)
        assert game.get_battlefield(p1).contains(small)
        assert not game.get_graveyard(p1).contains(small)
        assert game.get_graveyard(p1).contains(big)

    def test_minus2_no_eligible_creature_noop(self) -> None:
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        big = _creature("Big", "{4}{B}{B}")
        set_board_state(game, 0, graveyard=[big])
        ral.get_loyalty_abilities()[2].effect(game)
        assert game.get_graveyard(p1).contains(big)
        assert not game.get_battlefield(p1).contains(big)


class TestRalCoinFlips:
    def test_minus7_three_heads_skips_three_turns(self) -> None:
        game = create_game(scripts=([True, True, True, False, False], []))
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.get_loyalty_abilities()[3].effect(game)
        assert game.skipped_turns.get(1, 0) == 3

    def test_minus7_all_tails_no_skip(self) -> None:
        game = create_game(scripts=([False] * 5, []))
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.get_loyalty_abilities()[3].effect(game)
        assert game.skipped_turns.get(1, 0) == 0


class TestRalLoyaltyMechanics:
    def test_plus1_raises_loyalty_and_once_per_turn(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        _setup_sorcery_speed(game)

        ab = ral.get_loyalty_abilities()[0]
        inst = LoyaltyAbilityInstance(
            source=ral, controller=p1, loyalty_cost=ab.loyalty_cost, effect=ab.effect
        )
        activate_ability(game, p1, inst)
        assert ral.loyalty == 4
        _drain(game)

        with pytest.raises(AbilityError):
            activate_ability(game, p1, inst)
        assert ral.loyalty == 4

    def test_minus7_unaffordable_at_three(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        _setup_sorcery_speed(game)

        ab = ral.get_loyalty_abilities()[3]
        inst = LoyaltyAbilityInstance(
            source=ral, controller=p1, loyalty_cost=ab.loyalty_cost, effect=ab.effect
        )
        with pytest.raises(AbilityError):
            activate_ability(game, p1, inst)
        assert ral.loyalty == 3

    def test_dies_when_loyalty_hits_zero(self) -> None:
        clear_loyalty_tracking()
        game = create_game()
        p1, _ = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        small = _creature("Small", "{1}{B}")
        set_board_state(game, 0, battlefield=[ral], graveyard=[small])
        ral.loyalty = 2
        ral._resolve_target = small
        _setup_sorcery_speed(game)

        ab = ral.get_loyalty_abilities()[2]
        inst = LoyaltyAbilityInstance(
            source=ral, controller=p1, loyalty_cost=ab.loyalty_cost, effect=ab.effect
        )
        activate_ability(game, p1, inst)
        assert ral.loyalty == 0
        _drain(game)
        resolve_state_based_actions(game)

        assert game.get_graveyard(p1).contains(ral)
        assert game.get_battlefield(p1).contains(small)


class TestRalSkipIntegration:
    def test_skipped_turn_returns_to_controller(self) -> None:
        game = create_game()
        game.skipped_turns[1] = 1
        game.active_player_index = 0
        start_turn = game.turn_number
        guard = 0
        while game.turn_number == start_turn and guard < 100:
            game.advance_phase()
            guard += 1
        assert game.active_player_index == 0
        assert game.skipped_turns.get(1, 0) == 0
