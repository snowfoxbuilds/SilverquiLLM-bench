"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker)."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import LoyaltyAbilityInstance, activate_ability, clear_loyalty_tracking
from engine.card import Creature, Planeswalker
from engine.casting import resolve_top
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


class FakeRNG:
    """Deterministic coin source: returns the scripted 0/1 sequence."""

    def __init__(self, vals):
        self.vals = list(vals)
        self.i = 0

    def randint(self, a, b):
        v = self.vals[self.i % len(self.vals)]
        self.i += 1
        return v


def _ral(game, loyalty=None):
    pw = RalZarekGuestLecturer(owner=None)
    set_board_state(game, 0, battlefield=[pw])
    if loyalty is not None:
        pw.loyalty = loyalty
    return pw


def _activate(game, player, pw, index, targets=None):
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    clear_loyalty_tracking()
    ab = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(source=pw, controller=player,
                                  loyalty_cost=ab.loyalty_cost, effect=ab.effect,
                                  targets=targets or [])
    activate_ability(game, player, inst)
    resolve_top(game)


def _next_turn(game):
    t = game.turn_number
    while game.turn_number == t:
        game.advance_phase()


class TestProperties:
    def test_basic(self):
        pw = RalZarekGuestLecturer(owner=None)
        assert isinstance(pw, Planeswalker)
        assert pw.name == "Ral Zarek, Guest Lecturer"
        assert pw.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert pw.starting_loyalty == 3 and pw.loyalty == 3
        assert Supertype.LEGENDARY in pw.supertypes
        assert "Ral" in pw.subtypes


class TestPlusOneSurveil:
    def test_surveil_bins_top_keeps_second(self):
        game = create_game()
        p0 = game.players[0]
        pw = _ral(game)
        a = Creature(name="A", base_power=1, base_toughness=1)
        b = Creature(name="B", base_power=1, base_toughness=1)
        p0.zones[Zone.LIBRARY].add(a)   # second from top
        p0.zones[Zone.LIBRARY].add(b)   # top
        p0._script.extend([True, False])  # bin top (B), keep A
        _activate(game, p0, pw, 0)
        assert p0.zones[Zone.GRAVEYARD].contains(b)
        assert p0.zones[Zone.LIBRARY].contains(a)
        assert pw.loyalty == 4


class TestMinusOneDiscard:
    def test_target_player_discards(self):
        game = create_game()
        p0, p1 = game.players
        pw = _ral(game)
        card = Creature(name="Card", base_power=1, base_toughness=1)
        set_board_state(game, 1, hand=[card])
        p1._script.append(card)  # p1 chooses what to discard
        _activate(game, p0, pw, 1, targets=[p1])
        assert game.get_graveyard(p1).contains(card)
        assert pw.loyalty == 2

    def test_zero_target_players_is_noop(self):
        game = create_game()
        p0 = game.players[0]
        pw = _ral(game)
        _activate(game, p0, pw, 1, targets=[])
        assert pw.loyalty == 2  # loyalty still paid, nothing discarded


class TestMinusTwoReanimate:
    def test_reanimates_low_mv_creature(self):
        game = create_game()
        p0 = game.players[0]
        pw = _ral(game)
        gob = Creature(name="Goblin", mana_cost=ManaCost.parse("{1}{R}"),
                       base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[gob])
        _activate(game, p0, pw, 2, targets=[gob])
        assert game.get_battlefield(p0).contains(gob)
        assert not game.get_graveyard(p0).contains(gob)
        assert pw.loyalty == 1

    def test_high_mv_not_reanimated(self):
        game = create_game()
        p0 = game.players[0]
        pw = _ral(game)
        big = Creature(name="Big", mana_cost=ManaCost.parse("{3}{R}{R}"),
                       base_power=5, base_toughness=5)  # MV 5
        set_board_state(game, 0, graveyard=[big])
        _activate(game, p0, pw, 2, targets=[big])
        assert game.get_graveyard(p0).contains(big)  # stayed in graveyard
        assert not game.get_battlefield(p0).contains(big)


class TestMinusSevenSkipTurns:
    def test_three_heads_sets_skip_turns(self):
        game = create_game()
        p0, p1 = game.players
        pw = _ral(game, loyalty=7)
        game.rng = FakeRNG([1, 0, 1, 1, 0])  # 3 heads
        _activate(game, p0, pw, 3, targets=[p1])
        assert getattr(p1, "skip_turns", 0) == 3
        assert pw.loyalty == 0

    def test_zero_heads_no_skip(self):
        game = create_game()
        p0, p1 = game.players
        pw = _ral(game, loyalty=7)
        game.rng = FakeRNG([0, 0, 0, 0, 0])  # 0 heads
        _activate(game, p0, pw, 3, targets=[p1])
        assert getattr(p1, "skip_turns", 0) == 0

    def test_skip_turns_actually_skips(self):
        game = create_game()
        p0, p1 = game.players
        pw = _ral(game, loyalty=7)
        game.rng = FakeRNG([1, 1, 0, 0, 0])  # 2 heads
        _activate(game, p0, pw, 3, targets=[p1])
        assert p1.skip_turns == 2
        # Turn 1 was p0. p1's next two turns are skipped → p0 takes them.
        _next_turn(game)
        assert game.active_player is p0      # would-be p1 turn, skipped
        assert p1.skip_turns == 1
        _next_turn(game)
        assert game.active_player is p0      # p1's 2nd turn skipped
        assert p1.skip_turns == 0
        _next_turn(game)
        assert game.active_player is p1      # p1 resumes
