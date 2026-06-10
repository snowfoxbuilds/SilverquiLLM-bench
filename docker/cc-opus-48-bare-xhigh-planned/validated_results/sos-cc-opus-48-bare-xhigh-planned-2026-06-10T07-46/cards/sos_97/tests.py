"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker)."""

from __future__ import annotations

import random
from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _resolve_stack(game) -> None:
    from engine.state_based_actions import resolve_state_based_actions

    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _activate(game, p, pidx: int, pw, index: int, targets=None) -> None:
    clear_loyalty_tracking()
    game.active_player_index = pidx
    game.priority_player_index = pidx
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    if targets is not None:
        pw.chosen_targets = targets
    ab = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw, controller=p, loyalty_cost=ab.loyalty_cost, effect=ab.effect
    )
    activate_ability(game, p, inst)
    _resolve_stack(game)


def _lib_add(game, pidx, cards) -> None:
    p = game.players[pidx]
    for c in cards:
        c.owner = p
        c.controller = p
        p.zones[Zone.LIBRARY].add(c)


class TestProperties:
    def test_static_data(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert CardType.PLANESWALKER in card.card_types
        assert card.starting_loyalty == 3 and card.loyalty == 3
        assert "Ral" in card.subtypes
        assert Supertype.LEGENDARY in card.supertypes


class TestPlusOneSurveil:
    def test_surveil_bins_and_keeps(self) -> None:
        game = create_game(scripts=([True, False], []))  # bin top, keep next
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        deep = Sorcery(name="Deep", mana_cost=ManaCost.parse("{1}"))
        c2 = Sorcery(name="C2", mana_cost=ManaCost.parse("{1}"))
        c1 = Sorcery(name="C1", mana_cost=ManaCost.parse("{1}"))
        _lib_add(game, 0, [deep, c2, c1])  # top = c1, then c2
        _activate(game, p0, 0, ral, 0)
        assert game.get_graveyard(p0).contains(c1)  # binned
        assert game.get_library(p0).contains(c2)  # kept
        assert game.get_library(p0).contains(deep)
        assert ral.loyalty == 4


class TestMinusOneDiscard:
    def test_target_player_discards(self) -> None:
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        x = Sorcery(name="X", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 1, hand=[x])
        p1._script.append(x)  # p1 discards x
        _activate(game, p0, 0, ral, 1, targets=[p1])
        assert game.get_graveyard(p1).contains(x)
        assert ral.loyalty == 2

    def test_zero_target_players(self) -> None:
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        set_board_state(game, 1, hand=[Sorcery(name="Y", mana_cost=ManaCost.parse("{1}"))])
        _activate(game, p0, 0, ral, 1, targets=[])
        assert len(game.get_hand(p1).get_all()) == 1  # nobody discarded
        assert ral.loyalty == 2


class TestMinusTwoReanimate:
    def test_reanimate_small_creature(self) -> None:
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        critter = Creature(name="Critter", mana_cost=ManaCost.parse("{1}{G}"),
                           base_power=2, base_toughness=2)  # MV 2
        set_board_state(game, 0, graveyard=[critter])
        _activate(game, p0, 0, ral, 2, targets=[critter])
        assert game.get_battlefield(p0).contains(critter)
        assert not game.get_graveyard(p0).contains(critter)
        assert ral.loyalty == 1

    def test_does_not_reanimate_big_creature(self) -> None:
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        big = Creature(name="Big", mana_cost=ManaCost.parse("{4}"),
                       base_power=4, base_toughness=4)  # MV 4 > 3
        set_board_state(game, 0, graveyard=[big])
        _activate(game, p0, 0, ral, 2, targets=[big])
        assert game.get_graveyard(p0).contains(big)  # not reanimated
        assert not game.get_battlefield(p0).contains(big)


class TestMinusSevenSkipTurns:
    def test_sets_skip_turns_from_coin_flips(self) -> None:
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        _ref = random.Random(2024)
        expected = sum(_ref.randint(0, 1) for _ in range(5))
        game.rng = random.Random(2024)
        _activate(game, p0, 0, ral, 3, targets=[p1])
        assert p1.skip_turns == expected
        assert ral.loyalty == 0

    def test_turn_loop_skips_then_resumes(self) -> None:
        game = create_game()
        p0, p1 = game.players
        # p1 must skip their next turn.
        p1.skip_turns = 1
        assert game.active_player_index == 0  # turn 1 is p0
        while game.turn_number == 1:
            game.advance_phase()
        # Turn 2 would be p1's, but it is skipped → p0 again.
        assert game.active_player_index == 0
        assert p1.skip_turns == 0
        while game.turn_number == 2:
            game.advance_phase()
        # Turn 3 → p1 (skips exhausted).
        assert game.active_player_index == 1
