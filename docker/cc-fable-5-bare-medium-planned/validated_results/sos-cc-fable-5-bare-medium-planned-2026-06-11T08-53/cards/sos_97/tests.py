"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
)
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import ManaCost, Phase
from test_utils import create_game, set_board_state


def _setup(game) -> RalZarekGuestLecturer:
    pw = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[pw])
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return pw


def _activate(game, pw, index, targets=None) -> None:
    la = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw,
        controller=pw.controller,
        loyalty_cost=la.loyalty_cost,
        effect=la.effect,
        targets=list(targets or []),
    )
    activate_ability(game, game.players[0], inst)
    priority_loop(game)


def _fill_library(game, player_index, names):
    player = game.players[player_index]
    cards = []
    for name in names:
        c = Instant(name=name, mana_cost=ManaCost(generic=1))
        c.owner = c.controller = player
        game.get_library(player).add(c)
        cards.append(c)
    return cards


class TestRalZarek:
    def test_starting_loyalty(self) -> None:
        pw = RalZarekGuestLecturer()
        assert pw.starting_loyalty == 3 and pw.loyalty == 3

    def test_plus1_surveil_two(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        pw = _setup(game)
        bottom, middle, top = _fill_library(game, 0, ["Bottom", "Middle", "Top"])

        # Pass priority on the ability, then surveil decisions:
        # topmost ("Top") → graveyard, then "Middle" → keep on top.
        p1._script.extend(["pass", True, False])
        game.players[1]._script.extend(["pass"])
        _activate(game, pw, 0)

        assert pw.loyalty == 4
        assert game.get_graveyard(p1).contains(top)
        library = game.get_library(p1)
        assert library.top(1)[0] is middle
        assert library.contains(bottom)

    def test_minus1_each_target_player_discards(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        pw = _setup(game)
        c1 = Instant(name="P1 Card", mana_cost=ManaCost(generic=1))
        c2 = Instant(name="P2 Card", mana_cost=ManaCost(generic=1))
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])

        p1._script.extend(["pass", c1])
        p2._script.extend(["pass", c2])
        _activate(game, pw, 1, targets=[p1, p2])

        assert pw.loyalty == 2
        assert game.get_graveyard(p1).contains(c1)
        assert game.get_graveyard(p2).contains(c2)

    def test_minus1_zero_targets(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        pw = _setup(game)
        _activate(game, pw, 1, targets=[])
        assert pw.loyalty == 2  # cost paid, no effect

    def test_minus2_reanimates_small_creature(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        pw = _setup(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost(generic=2))
        set_board_state(game, 0, graveyard=[bear])

        _activate(game, pw, 2, targets=[bear])
        assert pw.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)

    def test_minus2_rejects_mv_above_three(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1 = game.players[0]
        pw = _setup(game)
        giant = Creature(name="Giant", base_power=5, base_toughness=5,
                         mana_cost=ManaCost(generic=5))
        set_board_state(game, 0, graveyard=[giant])

        _activate(game, pw, 2, targets=[giant])
        assert game.get_graveyard(p1).contains(giant)
        assert not game.get_battlefield(p1).contains(giant)

    def test_minus7_requires_loyalty(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = _setup(game)  # loyalty 3 < 7
        la = pw.get_loyalty_abilities()[3]
        inst = LoyaltyAbilityInstance(
            source=pw, controller=p1, loyalty_cost=la.loyalty_cost,
            effect=la.effect, targets=[p2],
        )
        try:
            activate_ability(game, p1, inst)
            raised = False
        except AbilityError:
            raised = True
        assert raised

    def test_minus7_coin_flips_skip_turns(self) -> None:
        game = create_game(scripts=(["pass"], ["pass"]))
        p1, p2 = game.players
        pw = _setup(game)
        pw.loyalty = 8
        game.rng = random.Random(7)
        ref_rng = random.Random(7)
        expected_heads = sum(ref_rng.randint(0, 1) for _ in range(5))

        _activate(game, pw, 3, targets=[p2])
        assert pw.loyalty == 1
        assert p2.skip_turns == expected_heads

        if expected_heads > 0:
            # End P1's turn: rotation must skip P2 and return to P1.
            from engine.types import Step
            from test_utils import advance_to_phase

            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            game.advance_phase()  # wrap to next turn
            assert game.active_player is p1
            assert p2.skip_turns == expected_heads - 1
