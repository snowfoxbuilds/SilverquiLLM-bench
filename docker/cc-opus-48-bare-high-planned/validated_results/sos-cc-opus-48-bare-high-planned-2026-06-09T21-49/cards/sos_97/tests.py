"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Planeswalker
from engine.types import CardType, ManaCost, Phase, Step, Supertype, Zone
from engine.state_based_actions import resolve_state_based_actions
from test_utils import create_game, set_board_state


def _sorcery_timing(game):
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


def _activate(game, pw, ctrl, index):
    clear_loyalty_tracking()
    ab = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(source=pw, controller=ctrl,
                                  loyalty_cost=ab.loyalty_cost, effect=ab.effect)
    activate_ability(game, ctrl, inst)
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _lib(game, pidx, cards):
    p = game.players[pidx]
    lib = p.zones[Zone.LIBRARY]
    for c in lib.get_all():
        lib.remove(c)
    for c in cards:
        c.owner = p
        c.controller = p
        lib.add(c)


class TestProperties:
    def test_static(self):
        c = RalZarekGuestLecturer(owner=None)
        assert isinstance(c, Planeswalker)
        assert c.starting_loyalty == 3
        assert c.loyalty == 3
        assert "Ral" in c.subtypes
        assert Supertype.LEGENDARY in c.supertypes
        assert c.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert len(c.get_loyalty_abilities()) == 4


class TestPlus1Surveil:
    def test_surveil_2(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[pw])
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        c3 = Creature(name="C3", base_power=1, base_toughness=1)
        _lib(game, 0, [c1, c2, c3])  # top two are c3 (top), c2
        _sorcery_timing(game)
        p0._script.extend([True, False])  # bin c3, keep c2
        _activate(game, pw, p0, 0)
        assert pw.loyalty == 4
        assert p0.zones[Zone.GRAVEYARD].contains(c3)
        assert p0.zones[Zone.LIBRARY].contains(c2)
        assert p0.zones[Zone.LIBRARY].contains(c1)


class TestMinus1Discard:
    def test_target_player_discards(self):
        game = create_game()
        p0, p1 = game.players
        pw = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[pw])
        card = Creature(name="Held", base_power=1, base_toughness=1)
        set_board_state(game, 1, hand=[card])
        _sorcery_timing(game)
        pw._resolve_targets = [p1]
        p1._script.append(card)
        _activate(game, pw, p0, 1)
        assert pw.loyalty == 2
        assert p1.zones[Zone.GRAVEYARD].contains(card)

    def test_zero_targets(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[pw])
        _sorcery_timing(game)
        pw._resolve_targets = []
        _activate(game, pw, p0, 1)
        assert pw.loyalty == 2  # cost paid, no discards


class TestMinus2Reanimate:
    def test_returns_small_creature(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p0, controller=p0)
        small = Creature(name="Small", mana_cost=ManaCost.parse("{2}"),
                         base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[pw], graveyard=[small])
        _sorcery_timing(game)
        pw._resolve_target = small
        _activate(game, pw, p0, 2)
        assert pw.loyalty == 1
        assert game.get_battlefield(p0).contains(small)
        assert not p0.zones[Zone.GRAVEYARD].contains(small)

    def test_big_creature_not_returned(self):
        game = create_game()
        p0 = game.players[0]
        pw = RalZarekGuestLecturer(owner=p0, controller=p0)
        big = Creature(name="Big", mana_cost=ManaCost.parse("{5}"),
                       base_power=5, base_toughness=5)
        set_board_state(game, 0, battlefield=[pw], graveyard=[big])
        _sorcery_timing(game)
        pw._resolve_target = big
        _activate(game, pw, p0, 2)
        assert p0.zones[Zone.GRAVEYARD].contains(big)  # MV 5 > 3 → stays
        assert not game.get_battlefield(p0).contains(big)


class TestMinus7Ultimate:
    def test_coin_flip_sets_skip_turns(self):
        game = create_game()
        p0, p1 = game.players
        pw = RalZarekGuestLecturer(owner=p0, controller=p0)
        pw.loyalty = 7
        set_board_state(game, 0, battlefield=[pw])
        _sorcery_timing(game)
        game.rng = random.Random(12345)
        # Compute the exact head count the card will see (same seed/sequence).
        ref = random.Random(12345)
        expected = sum(1 for _ in range(5) if ref.randint(0, 1) == 1)
        pw._resolve_target = p1
        _activate(game, pw, p0, 3)
        assert pw.loyalty == 0
        assert game.skip_turns.get(1, 0) == expected

    def test_skip_turn_mechanics(self):
        game = create_game()
        # Force p1 to skip one turn; advancing past end of turn should hand
        # the next turn back to p0 (p1's slot skipped).
        game.active_player_index = 0
        game._normal_next_index = 1
        game.skip_turns = {1: 1}
        game.phase = Phase.ENDING
        game.step = Step.CLEANUP
        game.advance_phase()  # wrap to next turn
        assert game.active_player_index == 0  # p1 was skipped
        assert game.skip_turns.get(1, 0) == 0
