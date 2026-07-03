"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


@pytest.fixture(autouse=True)
def _reset_loyalty():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


class FakeRng:
    """Deterministic coin flips: returns the supplied values in order."""

    def __init__(self, values):
        self._values = list(values)
        self._i = 0

    def randint(self, a, b):
        v = self._values[self._i]
        self._i += 1
        return v


def _lib_add(game, pidx, cards):
    p = game.players[pidx]
    for c in cards:
        c.owner = p
        c.controller = p
        p.zones[Zone.LIBRARY].add(c)


def _resolve_stack(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _sorcery_speed(game):
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _activate(game, player, ral, index, targets=None):
    ab = ral.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=ral, controller=player, loyalty_cost=ab.loyalty_cost,
        effect=ab.effect, targets=targets or [],
    )
    activate_ability(game, player, inst)
    _resolve_stack(game)


class TestProperties:
    def test_static(self):
        c = RalZarekGuestLecturer(owner=None)
        assert c.name == "Ral Zarek, Guest Lecturer"
        assert c.loyalty == 3 and c.starting_loyalty == 3
        assert "Ral" in c.subtypes
        assert Supertype.LEGENDARY in c.supertypes
        assert CardType.PLANESWALKER in c.card_types


class TestPlusOneSurveil:
    def test_surveil_bins_and_keeps(self):
        game = create_game(scripts=([True, False], []))  # bin top, keep second
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        _sorcery_speed(game)
        keep = Creature(name="Keep", base_power=1, base_toughness=1)
        binned = Creature(name="Binned", base_power=1, base_toughness=1)
        _lib_add(game, 0, [keep, binned])  # top = Binned
        _activate(game, p0, ral, 0)
        assert game.get_graveyard(p0).contains(binned)
        assert game.get_library(p0).contains(keep)
        assert ral.loyalty == 4


class TestMinusOneDiscard:
    def test_target_players_discard(self):
        junk0 = Creature(name="J0", base_power=1, base_toughness=1)
        junk1 = Creature(name="J1", base_power=1, base_toughness=1)
        game = create_game(scripts=([junk0], [junk1]))
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral], hand=[junk0])
        set_board_state(game, 1, hand=[junk1])
        _sorcery_speed(game)
        _activate(game, p0, ral, 1, targets=[p0, p1])
        assert game.get_graveyard(p0).contains(junk0)
        assert game.get_graveyard(p1).contains(junk1)
        assert ral.loyalty == 2

    def test_zero_target_players(self):
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        _sorcery_speed(game)
        _activate(game, p0, ral, 1, targets=[])  # no targets, no crash
        assert ral.loyalty == 2


class TestMinusTwoReanimate:
    def test_reanimates_small_creature(self):
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=None)
        small = Creature(name="Small", base_power=2, base_toughness=2,
                         mana_cost=ManaCost.parse("{1}{G}"))  # MV 2
        set_board_state(game, 0, battlefield=[ral], graveyard=[small])
        _sorcery_speed(game)
        _activate(game, p0, ral, 2, targets=[small])
        assert game.get_battlefield(p0).contains(small)
        assert not game.get_graveyard(p0).contains(small)
        assert ral.loyalty == 1

    def test_does_not_reanimate_big_creature(self):
        game = create_game()
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=None)
        big = Creature(name="Big", base_power=6, base_toughness=6,
                       mana_cost=ManaCost.parse("{4}{G}{G}"))  # MV 6
        set_board_state(game, 0, battlefield=[ral], graveyard=[big])
        _sorcery_speed(game)
        _activate(game, p0, ral, 2, targets=[big])
        assert game.get_graveyard(p0).contains(big)        # stayed in graveyard
        assert not game.get_battlefield(p0).contains(big)


class TestUltimate:
    def test_flip_coins_sets_skip_turns(self):
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        _sorcery_speed(game)
        game.rng = FakeRng([1, 0, 1, 1, 0])  # 3 heads
        _activate(game, p0, ral, 3, targets=[p1])
        assert p1.skip_turns == 3
        assert ral.loyalty == 0


class TestSkipTurnsIntegration:
    def test_opponent_skips_a_turn(self):
        game = create_game()
        p0, p1 = game.players
        p1.skip_turns = 1
        # advance through the rest of p0's turn 1 into the next turn
        start = game.turn_number
        for _ in range(40):
            game.advance_phase()
            if game.turn_number != start:
                break
        # p1's turn was skipped → p0 is active again on turn 2
        assert game.active_player_index == 0
        assert p1.skip_turns == 0
        # the following turn returns to p1
        start2 = game.turn_number
        for _ in range(40):
            game.advance_phase()
            if game.turn_number != start2:
                break
        assert game.active_player_index == 1
