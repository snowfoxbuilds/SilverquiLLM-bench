"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import AbilityError, activate_loyalty_ability_by_index
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state

MANA = {ManaType.BLACK: 2, ManaType.COLORLESS: 1}


def _cast_ral(game):
    ral = RalZarekGuestLecturer()
    set_board_state(game, 0, hand=[ral], mana=MANA)
    cast_spell(game, 0, "Ral Zarek, Guest Lecturer")
    assert game.players[0].zones[Zone.BATTLEFIELD].contains(ral)
    return ral


def _resolve(game, p1_choices=None):
    p1, p2 = game.players
    p1._script.append("pass")
    if p1_choices:
        p1._script.extend(p1_choices)
    p2._script.append("pass")
    priority_loop(game)


class TestStatics:
    def test_card_data(self):
        ral = RalZarekGuestLecturer()
        assert ral.name == "Ral Zarek, Guest Lecturer"
        assert ral.starting_loyalty == 3
        assert ral.loyalty == 3


class TestPlusOneSurveil:
    def test_surveil_two_bin_one_keep_one(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        deep = Creature(name="Deep", base_power=1, base_toughness=1)
        second = Creature(name="Second", base_power=1, base_toughness=1)
        top = Creature(name="Top", base_power=1, base_toughness=1)
        for c in (deep, second, top):
            c.owner = c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)

        activate_loyalty_ability_by_index(game, p1, ral, 0)
        # Bin "Top", keep "Second" on top.
        _resolve(game, p1_choices=[True, False])

        assert ral.loyalty == 4
        assert p1.zones[Zone.GRAVEYARD].contains(top)
        assert p1.zones[Zone.LIBRARY].get_all()[-1] is second


class TestMinusOneDiscard:
    def test_two_target_players_each_discard(self):
        game = create_game()
        p1, p2 = game.players
        ral = _cast_ral(game)
        c1 = Creature(name="C1", base_power=1, base_toughness=1)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])

        activate_loyalty_ability_by_index(game, p1, ral, 1, targets=[p1, p2])
        p1._script.extend(["pass", c1])
        p2._script.extend(["pass", c2])
        priority_loop(game)

        assert ral.loyalty == 2
        assert p1.zones[Zone.GRAVEYARD].contains(c1)
        assert p2.zones[Zone.GRAVEYARD].contains(c2)

    def test_zero_targets_no_discard(self):
        game = create_game()
        p1, p2 = game.players
        ral = _cast_ral(game)
        c2 = Creature(name="C2", base_power=1, base_toughness=1)
        set_board_state(game, 1, hand=[c2])

        activate_loyalty_ability_by_index(game, p1, ral, 1, targets=[])
        _resolve(game)

        assert ral.loyalty == 2
        assert p2.zones[Zone.HAND].contains(c2)


class TestMinusTwoReanimate:
    def test_returns_low_cost_creature_to_battlefield(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        cheap = Creature(name="Cheap", mana_cost=ManaCost.parse("{2}{G}"),
                         base_power=3, base_toughness=3)
        set_board_state(game, 0, graveyard=[cheap])

        activate_loyalty_ability_by_index(game, p1, ral, 2, targets=[cheap])
        _resolve(game)

        assert ral.loyalty == 1
        assert p1.zones[Zone.BATTLEFIELD].contains(cheap)
        assert not p1.zones[Zone.GRAVEYARD].contains(cheap)

    def test_mana_value_above_three_is_not_legal(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)
        big = Creature(name="Big", mana_cost=ManaCost.parse("{3}{G}"),
                       base_power=4, base_toughness=4)
        set_board_state(game, 0, graveyard=[big])

        activate_loyalty_ability_by_index(game, p1, ral, 2, targets=[big])
        _resolve(game)

        # MV 4 > 3: the ability does nothing (loyalty was still paid).
        assert ral.loyalty == 1
        assert p1.zones[Zone.GRAVEYARD].contains(big)
        assert not p1.zones[Zone.BATTLEFIELD].contains(big)


class TestMinusSevenUltimate:
    def test_requires_loyalty_seven(self):
        game = create_game()
        p1 = game.players[0]
        ral = _cast_ral(game)  # loyalty 3
        with pytest.raises(AbilityError):
            activate_loyalty_ability_by_index(game, p1, ral, 3)

    def test_opponent_skips_turns_equal_to_heads(self):
        game = create_game()
        p1, p2 = game.players
        ral = _cast_ral(game)
        ral.loyalty = 9
        game.rng = random.Random(7)
        reference_rng = random.Random(7)
        expected_heads = sum(reference_rng.randint(0, 1) for _ in range(5))
        assert expected_heads > 0  # seed sanity

        activate_loyalty_ability_by_index(game, p1, ral, 3, targets=[p2])
        _resolve(game)

        assert ral.loyalty == 2
        assert p2.skip_turns == expected_heads

        # p1's turn ends; p2's next turns are skipped, so p1 goes again.
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()
        assert game.active_player is p1
        assert p2.skip_turns == expected_heads - 1
