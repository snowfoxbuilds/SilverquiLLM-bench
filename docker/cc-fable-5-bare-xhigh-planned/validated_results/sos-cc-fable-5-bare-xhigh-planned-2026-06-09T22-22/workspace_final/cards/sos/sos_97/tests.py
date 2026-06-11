"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Planeswalker
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, Phase, Supertype
from test_utils import create_game, set_board_state


class FakeRng:
    def __init__(self, values):
        self._values = list(values)
        self._i = 0

    def randint(self, a, b):
        v = self._values[self._i % len(self._values)]
        self._i += 1
        return v


def _sorcery_speed(game, pi=0):
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = pi
    game.priority_player_index = pi


def _activate(game, ral, p, index):
    clear_loyalty_tracking()
    ab = ral.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(source=ral, controller=p,
                                  loyalty_cost=ab.loyalty_cost, effect=ab.effect)
    activate_ability(game, p, inst)


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)
        resolve_state_based_actions(game)


def _lib_add(game, pi, card):
    p = game.players[pi]
    card.owner = p
    card.controller = p
    game.get_library(p).add(card)


def _names(zone):
    return [getattr(c, "name", "?") for c in zone.get_all()]


class TestProperties:
    def test_basics(self):
        c = RalZarekGuestLecturer(owner=None)
        assert isinstance(c, Planeswalker)
        assert c.name == "Ral Zarek, Guest Lecturer"
        assert c.starting_loyalty == 3 and c.loyalty == 3
        assert "Ral" in c.subtypes
        assert Supertype.LEGENDARY in c.supertypes


class TestSurveil:
    def test_bin_top_keep_second(self):
        game = create_game(scripts=([True, False], []))
        p0 = game.players[0]
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        _lib_add(game, 0, Creature(name="Second", base_power=1, base_toughness=1))
        _lib_add(game, 0, Creature(name="Top", base_power=1, base_toughness=1))  # top
        _sorcery_speed(game)
        _activate(game, ral, p0, 0)
        _drain(game)
        assert "Top" in _names(game.get_graveyard(p0))
        assert "Second" in _names(game.get_library(p0))
        assert ral.loyalty == 4  # +1


class TestDiscard:
    def test_target_players_discard(self):
        game = create_game()
        p0, p1 = game.players
        trash = Creature(name="Trash", base_power=1, base_toughness=1)
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral])
        set_board_state(game, 1, hand=[trash])
        p1._script.appendleft(trash)
        ral._resolve_targets = [p1]
        _sorcery_speed(game)
        _activate(game, ral, p0, 1)
        _drain(game)
        assert "Trash" in _names(game.get_graveyard(p1))
        assert ral.loyalty == 2  # -1


class TestReanimate:
    def test_returns_small_creature(self):
        game = create_game()
        p0 = game.players[0]
        dead = Creature(name="Goblin", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{R}"))
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral], graveyard=[dead])
        ral._resolve_target = dead
        _sorcery_speed(game)
        _activate(game, ral, p0, 2)
        _drain(game)
        assert "Goblin" in _names(game.get_battlefield(p0))
        assert "Goblin" not in _names(game.get_graveyard(p0))
        assert ral.loyalty == 1  # -2

    def test_high_mv_not_returned(self):
        game = create_game()
        p0 = game.players[0]
        big = Creature(name="Dragon", base_power=5, base_toughness=5,
                       mana_cost=ManaCost.parse("{4}{R}"))  # mv 5 > 3
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, battlefield=[ral], graveyard=[big])
        ral._resolve_target = big
        _sorcery_speed(game)
        _activate(game, ral, p0, 2)
        _drain(game)
        assert "Dragon" not in _names(game.get_battlefield(p0))
        assert "Dragon" in _names(game.get_graveyard(p0))


class TestUltimate:
    def test_skip_counter_set_to_heads(self):
        game = create_game()
        p0, p1 = game.players
        game.rng = FakeRng([1, 1, 0, 1, 1])  # 4 heads
        ral = RalZarekGuestLecturer(owner=None)
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        ral._resolve_target = p1
        _sorcery_speed(game)
        _activate(game, ral, p0, 3)
        _drain(game)
        assert game._skip_turns[1] == 4
        assert ral.loyalty == 0  # -7

    def test_zero_heads_skips_nothing(self):
        game = create_game()
        p0, p1 = game.players
        game.rng = FakeRng([0, 0, 0, 0, 0])
        ral = RalZarekGuestLecturer(owner=None)
        ral.loyalty = 7
        set_board_state(game, 0, battlefield=[ral])
        ral._resolve_target = p1
        _sorcery_speed(game)
        _activate(game, ral, p0, 3)
        _drain(game)
        assert game._skip_turns.get(1, 0) == 0

    def test_skip_turns_rotation(self):
        # A skipped player loses exactly that many turns in rotation.
        game = create_game()
        game._skip_turns = {1: 1}
        starts = []
        last_turn = game.turn_number
        for _ in range(400):
            game.advance_phase()
            if game.turn_number != last_turn:
                starts.append(game.active_player_index)
                last_turn = game.turn_number
            if len(starts) >= 3:
                break
        # Turn 1 was p0; p1 skipped once → p0 again; then p1.
        assert starts[0] == 0
        assert starts[1] == 1
