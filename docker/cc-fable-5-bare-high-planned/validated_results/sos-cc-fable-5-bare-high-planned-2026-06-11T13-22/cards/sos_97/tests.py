"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
)
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _activate(game, pw, index, targets=None):
    player = pw.controller
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.players.index(player)
    ab = pw.get_loyalty_abilities()[index]
    activate_ability(game, player, LoyaltyAbilityInstance(
        source=pw, controller=player, loyalty_cost=ab.loyalty_cost,
        effect=ab.effect, targets=list(targets or []),
    ))


def _setup(p1_extra_script=None):
    game = create_game(scripts=(
        (p1_extra_script or []) + ["pass"] * 10, ["pass"] * 10,
    ))
    pw = RalZarekGuestLecturer(owner=None)
    set_board_state(game, 0, battlefield=[pw])
    return game, pw


class TestRalZarek:
    def test_cast_enters_with_three_loyalty(self):
        game = create_game()
        pw = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, hand=[pw],
                        mana={ManaType.BLACK: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Ral Zarek, Guest Lecturer")
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(pw)
        assert pw.loyalty == 3

    def test_plus1_surveil_two(self):
        game, pw = _setup()
        p1 = game.players[0]
        a = Creature(name="A", base_power=1, base_toughness=1)
        b = Creature(name="B", base_power=1, base_toughness=1)
        c = Creature(name="C", base_power=1, base_toughness=1)
        for card in (a, b, c):   # top of library = c
            card.owner = card.controller = p1
            p1.zones[Zone.LIBRARY].add(card)

        _activate(game, pw, 0)
        # pass, pass -> resolve: bin C (top), keep B.
        from collections import deque
        p1._script = deque(["pass", True, False] + ["pass"] * 6)
        priority_loop(game)

        assert pw.loyalty == 4
        assert p1.zones[Zone.GRAVEYARD].contains(c)
        assert p1.zones[Zone.LIBRARY].top(1)[0] is b

    def test_minus1_target_players_each_discard(self):
        game, pw = _setup()
        p1, p2 = game.players
        h1 = Creature(name="H1", base_power=1, base_toughness=1)
        h2 = Creature(name="H2", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[h1])
        set_board_state(game, 1, hand=[h2])

        _activate(game, pw, 1, targets=[p1, p2])
        from collections import deque
        p1._script = deque(["pass", h1] + ["pass"] * 6)
        p2._script = deque(["pass", h2] + ["pass"] * 6)
        priority_loop(game)

        assert pw.loyalty == 2
        assert p1.zones[Zone.GRAVEYARD].contains(h1)
        assert p2.zones[Zone.GRAVEYARD].contains(h2)

    def test_minus2_reanimates_mv3_or_less(self):
        game, pw = _setup()
        p1 = game.players[0]
        cheap = Creature(name="Cheap", mana_cost=ManaCost.parse("{2}{B}"),
                         base_power=3, base_toughness=2)
        set_board_state(game, 0, graveyard=[cheap])

        _activate(game, pw, 2, targets=[cheap])
        priority_loop(game)

        assert pw.loyalty == 1
        assert p1.zones[Zone.BATTLEFIELD].contains(cheap)
        assert not p1.zones[Zone.GRAVEYARD].contains(cheap)

    def test_minus2_mv4_target_fizzles(self):
        game, pw = _setup()
        p1 = game.players[0]
        fat = Creature(name="Fat", mana_cost=ManaCost.parse("{3}{B}"),
                       base_power=5, base_toughness=5)
        set_board_state(game, 0, graveyard=[fat])

        _activate(game, pw, 2, targets=[fat])
        priority_loop(game)

        assert p1.zones[Zone.GRAVEYARD].contains(fat)   # MV 4 — not returned
        assert pw.loyalty == 1                          # cost was still paid

    def test_minus7_needs_seven_loyalty(self):
        game, pw = _setup()
        with pytest.raises(AbilityError):
            _activate(game, pw, 3, targets=[game.players[1]])
        assert pw.loyalty == 3

    def test_minus7_coin_flips_skip_turns(self):
        game, pw = _setup()
        p1, p2 = game.players
        pw.loyalty = 9
        game.rng.seed(123)
        mirror_rng = random.Random(123)
        expected_heads = sum(mirror_rng.randint(0, 1) for _ in range(5))

        _activate(game, pw, 3, targets=[p2])
        priority_loop(game)

        assert pw.loyalty == 2
        assert p2.skip_turns == expected_heads

        # Drive turn rotation: P2 must not become active until the skips
        # are consumed.
        skipped = 0
        for _ in range(expected_heads + 1):
            current_turn = game.turn_number
            while game.turn_number == current_turn:
                game.advance_phase()
            if skipped < expected_heads:
                assert game.active_player is p1
                skipped += 1
            else:
                assert game.active_player is p2
        assert p2.skip_turns == 0

    def test_once_per_turn(self):
        game, pw = _setup()
        _activate(game, pw, 0)
        priority_loop(game)
        with pytest.raises(AbilityError):
            _activate(game, pw, 1, targets=[])
