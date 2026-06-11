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
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import ManaCost, Phase, Zone
from test_utils import create_game, set_board_state


@pytest.fixture(autouse=True)
def _fresh_loyalty_tracking():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _activate(game, player_index, pw, ability_index, targets=None):
    """Activate a loyalty ability through the real ability pipeline."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    if targets is not None:
        pw.chosen_targets = targets
    ability = pw.get_loyalty_abilities()[ability_index]
    activate_ability(
        game,
        player,
        LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
            description=ability.description,
        ),
    )
    game.players[0]._script.appendleft("pass")
    game.players[1]._script.appendleft("pass")
    priority_loop(game)


class TestProperties:
    def test_static_data(self) -> None:
        pw = RalZarekGuestLecturer(owner=None)
        assert pw.name == "Ral Zarek, Guest Lecturer"
        assert pw.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert pw.starting_loyalty == 3 and pw.loyalty == 3
        assert "Ral" in pw.subtypes
        assert len(pw.get_loyalty_abilities()) == 4


class TestPlusOneSurveil:
    def test_surveil_two_bin_one_keep_one(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        pw = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[pw])
        bottom = Creature(name="Bottom", base_power=1, base_toughness=1)
        keep = Creature(name="Keep", base_power=1, base_toughness=1)
        bin_me = Instant(name="BinMe", mana_cost=ManaCost.parse("{U}"))
        for c in (bottom, keep, bin_me):       # BinMe ends up on top
            c.owner = c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)

        # Top card (BinMe): yes; next (Keep): no.
        p1._script.extend([True, False])
        _activate(game, 0, pw, 0)

        assert pw.loyalty == 4
        assert game.get_graveyard(p1).contains(bin_me)
        assert p1.zones[Zone.LIBRARY].top(1) == [keep]   # still on top


class TestMinusOneDiscard:
    def test_each_target_player_discards(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        pw = RalZarekGuestLecturer()
        mine = Instant(name="Mine", mana_cost=ManaCost.parse("{U}"))
        theirs = Instant(name="Theirs", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, battlefield=[pw], hand=[mine])
        set_board_state(game, 1, hand=[theirs])

        p1._script.extend([mine])
        p2._script.extend([theirs])
        _activate(game, 0, pw, 1, targets=[p1, p2])

        assert pw.loyalty == 2
        assert game.get_graveyard(p1).contains(mine)
        assert game.get_graveyard(p2).contains(theirs)

    def test_zero_targets_nothing_happens(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        pw = RalZarekGuestLecturer()
        keeper = Instant(name="Keeper", mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, battlefield=[pw], hand=[keeper])

        _activate(game, 0, pw, 1, targets=[])

        assert pw.loyalty == 2
        assert game.get_hand(p1).contains(keeper)


class TestMinusTwoReanimate:
    def test_returns_cheap_creature_to_battlefield(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        pw = RalZarekGuestLecturer()
        cheap = Creature(name="Cheap", mana_cost=ManaCost.parse("{2}{B}"),
                         base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[pw], graveyard=[cheap])

        _activate(game, 0, pw, 2, targets=[cheap])

        assert pw.loyalty == 1
        assert game.get_battlefield(p1).contains(cheap)
        assert not game.get_graveyard(p1).contains(cheap)

    def test_mv_above_three_stays_in_graveyard(self) -> None:
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        pw = RalZarekGuestLecturer()
        big = Creature(name="Big", mana_cost=ManaCost.parse("{3}{B}"),
                       base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[pw], graveyard=[big])

        _activate(game, 0, pw, 2, targets=[big])

        assert pw.loyalty == 1                      # cost still paid
        assert game.get_graveyard(p1).contains(big)


class TestMinusSevenUltimate:
    def test_requires_loyalty_seven(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        pw = RalZarekGuestLecturer()                # loyalty 3
        set_board_state(game, 0, battlefield=[pw])
        ability = pw.get_loyalty_abilities()[3]
        with pytest.raises(AbilityError):
            game.phase = Phase.PRECOMBAT_MAIN
            game.step = None
            activate_ability(
                game,
                p1,
                LoyaltyAbilityInstance(
                    source=pw, controller=p1,
                    loyalty_cost=ability.loyalty_cost, effect=ability.effect,
                ),
            )

    def test_coin_flips_set_skip_turns_and_turns_are_skipped(self) -> None:
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        pw = RalZarekGuestLecturer()
        set_board_state(game, 0, battlefield=[pw])
        pw.loyalty = 7
        game.rng = random.Random(7)
        reference_rng = random.Random(7)
        expected_heads = sum(reference_rng.randint(0, 1) for _ in range(5))
        assert expected_heads > 0                  # seed sanity for this test

        _activate(game, 0, pw, 3, targets=[p2])

        assert pw.loyalty == 0
        assert p2.skip_turns == expected_heads

        # Walk the turn cycle: p2's next turns are consumed as skips, so
        # the next expected_heads turn(s) belong to p1 again.
        from test_utils import advance_to_phase

        for _ in range(expected_heads):
            advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
            assert game.active_player is p1
        assert p2.skip_turns == 0

        # And after the skips are used up, p2 finally gets a turn.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
