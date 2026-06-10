"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

import pytest

from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import ManaCost, Phase, Zone
from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from test_utils import advance_to_phase, create_game, set_board_state


def _activate_loyalty(game, player, pw, index: int) -> None:
    """Activate a printed loyalty ability by index through the engine."""
    ability = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw,
        controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
    )
    activate_ability(game, player, inst)
    priority_loop(game)


def _game_with_ral(p1_script=None, p2_script=None):
    game = create_game(scripts=((p1_script or []), (p2_script or [])))
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    clear_loyalty_tracking()
    p1 = game.players[0]
    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, battlefield=[ral])
    return game, p1, game.players[1], ral


class TestPlusOneSurveil:
    def test_surveil_2_bins_chosen_cards(self) -> None:
        """Bin the top card, keep the second; loyalty 3 → 4."""
        game, p1, p2, ral = _game_with_ral(
            p1_script=["pass", True, False], p2_script=["pass"])
        top = Instant(name="Top")
        second = Instant(name="Second")
        for c in (second, top):  # 'top' added last → on top
            c.owner = p1
            p1.zones[Zone.LIBRARY].add(c)
        _activate_loyalty(game, p1, ral, 0)
        assert p1.zones[Zone.GRAVEYARD].contains(top)
        assert p1.zones[Zone.LIBRARY].top(1) == [second]
        assert ral.loyalty == 4

    def test_surveil_with_one_card_library(self) -> None:
        game, p1, p2, ral = _game_with_ral(
            p1_script=["pass", False], p2_script=["pass"])
        only = Instant(name="Only")
        only.owner = p1
        p1.zones[Zone.LIBRARY].add(only)
        _activate_loyalty(game, p1, ral, 0)
        assert p1.zones[Zone.LIBRARY].contains(only)
        assert ral.loyalty == 4


class TestMinusOneDiscard:
    def test_each_target_player_discards(self) -> None:
        game, p1, p2, ral = _game_with_ral(
            p1_script=["pass"], p2_script=["pass"])
        mine = Instant(name="Mine")
        theirs = Instant(name="Theirs")
        set_board_state(game, 0, battlefield=[ral], hand=[mine])
        set_board_state(game, 1, hand=[theirs])
        p1._script.append(mine)    # p1's discard choice
        p2._script.append(theirs)  # p2's discard choice
        ral.chosen_targets = [p1, p2]
        _activate_loyalty(game, p1, ral, 1)
        assert p1.zones[Zone.GRAVEYARD].contains(mine)
        assert p2.zones[Zone.GRAVEYARD].contains(theirs)
        assert ral.loyalty == 2

    def test_zero_target_players(self) -> None:
        game, p1, p2, ral = _game_with_ral(
            p1_script=["pass"], p2_script=["pass"])
        keep = Instant(name="Keep")
        set_board_state(game, 0, battlefield=[ral], hand=[keep])
        ral.chosen_targets = []
        _activate_loyalty(game, p1, ral, 1)
        assert p1.zones[Zone.HAND].contains(keep)
        assert ral.loyalty == 2


class TestMinusTwoReanimate:
    def test_returns_creature_mv3_or_less(self) -> None:
        game, p1, p2, ral = _game_with_ral(
            p1_script=["pass"], p2_script=["pass"])
        bear = Creature(name="Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[ral], graveyard=[bear])
        ral.chosen_targets = [bear]
        _activate_loyalty(game, p1, ral, 2)
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)
        assert ral.loyalty == 1

    def test_mv_4_creature_is_not_returned(self) -> None:
        game, p1, p2, ral = _game_with_ral(
            p1_script=["pass"], p2_script=["pass"])
        ogre = Creature(name="Ogre", mana_cost=ManaCost.parse("{3}{R}"),
                        base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[ral], graveyard=[ogre])
        ral.chosen_targets = [ogre]
        _activate_loyalty(game, p1, ral, 2)
        assert p1.zones[Zone.GRAVEYARD].contains(ogre)
        assert not p1.zones[Zone.BATTLEFIELD].contains(ogre)


class TestUltimate:
    def test_requires_seven_loyalty(self) -> None:
        game, p1, p2, ral = _game_with_ral()
        ral.chosen_targets = [p2]
        ability = ral.get_loyalty_abilities()[3]
        inst = LoyaltyAbilityInstance(source=ral, controller=p1,
                                      loyalty_cost=ability.loyalty_cost,
                                      effect=ability.effect)
        with pytest.raises(AbilityError):
            activate_ability(game, p1, inst)  # only 3 loyalty

    def test_coin_flips_set_skip_turns_and_turns_are_skipped(self) -> None:
        game, p1, p2, ral = _game_with_ral(
            p1_script=["pass"], p2_script=["pass"])
        ral.loyalty = 7
        game.rng = random.Random(7)
        _predict = random.Random(7)
        expected_heads = sum(_predict.randint(0, 1) for _ in range(5))
        assert expected_heads > 0  # seed chosen to produce at least one head
        ral.chosen_targets = [p2]
        _activate_loyalty(game, p1, ral, 3)
        assert ral.loyalty == 0
        assert getattr(p2, "skip_turns", 0) == expected_heads

        # P2's next turns are actually skipped by the turn loop.
        for _ in range(expected_heads):
            advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)  # wraps to a new turn
            assert game.active_player is p1  # p2's turn was skipped
        assert getattr(p2, "skip_turns", 0) == 0
        # After the skips are consumed, P2 finally gets a turn.
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        assert game.active_player is p2
