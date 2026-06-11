"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Phase, Supertype
from test_utils import create_game, set_board_state


def _setup(game):
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    clear_loyalty_tracking()


def _set_library(game, idx, cards):
    lib = game.get_library(game.players[idx])
    for o in lib.get_all():
        lib.remove(o)
    for c in cards:
        c.owner = game.players[idx]
        c.controller = game.players[idx]
        lib.add(c)


def _activate(game, player, pw, index, targets=None):
    la = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw, controller=player, loyalty_cost=la.loyalty_cost,
        effect=la.effect, targets=targets or [],
    )
    activate_ability(game, player, inst)
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


class _Coins:
    """Deterministic coin source: returns the given sequence of 0/1."""

    def __init__(self, seq):
        self.seq = list(seq)
        self.i = 0

    def randint(self, a, b):
        v = self.seq[self.i]
        self.i += 1
        return v


class TestProperties:
    def test_static(self):
        c = RalZarekGuestLecturer(owner=None)
        assert c.name == "Ral Zarek, Guest Lecturer"
        assert c.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert c.starting_loyalty == 3 and c.loyalty == 3
        assert Supertype.LEGENDARY in c.supertypes
        assert CardType.PLANESWALKER in c.card_types


class TestSurveil:
    def test_plus1_bins_and_keeps(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        a = Creature(name="Keep", base_power=1, base_toughness=1)
        b = Creature(name="Bin", base_power=1, base_toughness=1)
        _set_library(game, 0, [a, b])  # b is top, a second
        _setup(game)
        p0 = game.players[0]
        p0._script.extend([True, False])  # bin top (b), keep a
        _activate(game, p0, ral, 0)
        assert ral.loyalty == 4
        assert game.get_graveyard(p0).contains(b)
        assert game.get_library(p0).contains(a)
        assert not game.get_library(p0).contains(b)


class TestDiscard:
    def test_minus1_targets_discard(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        c0 = Creature(name="P0Card", base_power=1, base_toughness=1)
        c1 = Creature(name="P1Card", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[ral], hand=[c0])
        set_board_state(game, 1, hand=[c1])
        _setup(game)
        p0, p1 = game.players
        p0._script.append(c0)
        p1._script.append(c1)
        _activate(game, p0, ral, 1, targets=[p0, p1])
        assert ral.loyalty == 2
        assert game.get_graveyard(p0).contains(c0)
        assert game.get_graveyard(p1).contains(c1)

    def test_minus1_no_targets_is_noop(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        _setup(game)
        p0 = game.players[0]
        _activate(game, p0, ral, 1, targets=[])
        assert ral.loyalty == 2  # cost still paid


class TestReanimate:
    def test_minus2_returns_small_creature(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        small = Creature(name="Small", mana_cost=ManaCost.parse("{2}"),
                         base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[ral], graveyard=[small])
        _setup(game)
        p0 = game.players[0]
        _activate(game, p0, ral, 2, targets=[small])
        assert ral.loyalty == 1
        assert game.get_battlefield(p0).contains(small)
        assert not game.get_graveyard(p0).contains(small)

    def test_minus2_rejects_high_mv(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        big = Creature(name="Big", mana_cost=ManaCost.parse("{4}"),
                       base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[ral], graveyard=[big])
        _setup(game)
        p0 = game.players[0]
        _activate(game, p0, ral, 2, targets=[big])
        assert game.get_graveyard(p0).contains(big)
        assert not game.get_battlefield(p0).contains(big)


class TestUltimate:
    def test_minus7_requires_loyalty(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        _setup(game)
        p0 = game.players[0]
        import pytest
        with pytest.raises(Exception):
            _activate(game, p0, ral, 3, targets=[game.players[1]])

    def test_minus7_sets_skip_turns_to_heads(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        _setup(game)
        game.rng = _Coins([1, 1, 0, 1, 0])  # 3 heads
        p0, p1 = game.players
        _activate(game, p0, ral, 3, targets=[p1])
        assert ral.loyalty == 0
        assert p1.skip_turns == 3

    def test_minus7_zero_heads(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        _setup(game)
        game.rng = _Coins([0, 0, 0, 0, 0])
        p0, p1 = game.players
        _activate(game, p0, ral, 3, targets=[p1])
        assert p1.skip_turns == 0


class TestSkipTurnRotation:
    def test_skip_two_turns(self):
        game = create_game()  # turn 1, active 0
        game.players[1].skip_turns = 2
        records = {1: game.active_player_index}
        last_turn = game.turn_number
        for _ in range(300):
            game.advance_phase()
            if game.turn_number != last_turn:
                last_turn = game.turn_number
                records[last_turn] = game.active_player_index
            if last_turn >= 5:
                break
        # p1's next two turns (2 and 3) are skipped; p0 takes them.
        assert records[1] == 0
        assert records[2] == 0
        assert records[3] == 0
        assert records[4] == 1
        assert records[5] == 0
