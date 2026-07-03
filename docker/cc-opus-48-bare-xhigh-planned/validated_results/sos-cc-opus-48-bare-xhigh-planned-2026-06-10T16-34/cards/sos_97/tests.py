"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _resolve_all(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _activate(game, player, pw, index, targets=None):
    clear_loyalty_tracking()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    if targets is not None:
        pw.chosen_targets = list(targets)
    la = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw, controller=player, loyalty_cost=la.loyalty_cost, effect=la.effect
    )
    activate_ability(game, player, inst)
    _resolve_all(game)


def _lib_add(player, card):
    card.owner = player
    card.controller = player
    player.zones[Zone.LIBRARY].add(card)


def _next_turn(game):
    start = game.turn_number
    while game.turn_number == start:
        game.advance_phase()


class TestProperties:
    def test_static(self):
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert card.starting_loyalty == 3
        assert card.loyalty == 3
        assert Supertype.LEGENDARY in card.supertypes
        assert "Ral" in card.subtypes

    def test_four_abilities(self):
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert [a.loyalty_cost for a in abilities] == [1, -1, -2, -7]


class TestPlusOneSurveil:
    def test_surveil_bin_and_keep(self):
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        a = Creature(name="A", base_power=1, base_toughness=1)
        b = Creature(name="B", base_power=1, base_toughness=1)
        _lib_add(p1, a)
        _lib_add(p1, b)  # b is the top card
        # looked order: b (top) then a. Bin b, keep a.
        p1._script.extend([True, False])
        _activate(game, p1, ral, 0)
        assert ral.loyalty == 4
        assert game.get_graveyard(p1).contains(b)
        assert game.get_library(p1).contains(a)
        assert not game.get_library(p1).contains(b)


class TestMinusOneDiscard:
    def test_target_players_discard(self):
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        c1 = Creature(name="P1Card", base_power=1, base_toughness=1)
        c2 = Creature(name="P2Card", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[ral], hand=[c1])
        set_board_state(game, 1, hand=[c2])
        p1._script.append(c1)  # p1 discards c1
        p2._script.append(c2)  # p2 discards c2
        _activate(game, p1, ral, 1, targets=[p1, p2])
        assert ral.loyalty == 2
        assert game.get_graveyard(p1).contains(c1)
        assert game.get_graveyard(p2).contains(c2)

    def test_zero_targets_noop(self):
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        _activate(game, p1, ral, 1, targets=[])
        assert ral.loyalty == 2  # cost still paid, nothing discarded


class TestMinusTwoReanimate:
    def test_reanimate_small_creature(self):
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[ral], graveyard=[bear])
        _activate(game, p1, ral, 2, targets=[bear])
        assert ral.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)

    def test_high_mv_creature_not_returned(self):
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        giant = Creature(name="Giant", mana_cost=ManaCost.parse("{4}{G}"),
                         base_power=6, base_toughness=6)
        set_board_state(game, 0, battlefield=[ral], graveyard=[giant])
        _activate(game, p1, ral, 2, targets=[giant])
        assert ral.loyalty == 1
        assert game.get_graveyard(p1).contains(giant)  # MV 5 > 3 → stays
        assert not game.get_battlefield(p1).contains(giant)


class TestMinusSevenUltimate:
    def test_requires_seven_loyalty(self):
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)  # loyalty 3
        set_board_state(game, 0, battlefield=[ral])
        with pytest.raises(AbilityError):
            _activate(game, p1, ral, 3, targets=[p2])

    def test_skip_turns_equals_heads(self):
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        game.rng = random.Random(42)
        # Expected heads computed from the same seeded sequence the card uses.
        r = random.Random(42)
        expected = sum(1 for _ in range(5) if r.randint(0, 1) == 1)
        _activate(game, p1, ral, 3, targets=[p2])
        assert ral.loyalty == 0
        assert p2.skip_turns == expected


class TestSkipTurnsMechanic:
    def test_player_skips_two_turns(self):
        game = create_game()  # turn 1, p1 active; p2 is next
        p1, p2 = game.players
        p2.skip_turns = 2
        _next_turn(game)
        assert game.active_player_index == 0  # p2 skipped → p1 again
        assert p2.skip_turns == 1
        _next_turn(game)
        assert game.active_player_index == 0  # p2 skipped again
        assert p2.skip_turns == 0
        _next_turn(game)
        assert game.active_player_index == 1  # p2 finally takes a turn
        _next_turn(game)
        assert game.active_player_index == 0  # normal rotation resumes
