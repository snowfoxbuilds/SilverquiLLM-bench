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
from engine.casting import resolve_top
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _activate_loyalty(game, player, pw, index, targets=None):
    """Activate a printed loyalty ability through the engine's ability path."""
    pw.chosen_targets = list(targets or [])
    ability = pw.get_loyalty_abilities()[index]
    activate_ability(
        game,
        player,
        LoyaltyAbilityInstance(
            source=pw,
            controller=player,
            loyalty_cost=ability.loyalty_cost,
            effect=ability.effect,
        ),
    )
    resolve_top(game)


def _setup(loyalty=None):
    game = create_game()
    p1 = game.players[0]
    ral = RalZarekGuestLecturer(owner=p1)
    set_board_state(game, 0, battlefield=[ral])
    if loyalty is not None:
        ral.loyalty = loyalty
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    return game, p1, ral


def _stock_library(game, player_index, names):
    """names[0] ends up on top of the library."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for name in reversed(names):
        card = Creature(name=name, base_power=1, base_toughness=1)
        card.owner = player
        card.controller = player
        library.add(card)


class TestRalZarekBasics:
    def test_cast_enters_with_three_loyalty(self):
        game = create_game()
        ral = RalZarekGuestLecturer(owner=None)
        set_board_state(game, 0, hand=[ral],
                        mana={ManaType.BLACK: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Ral Zarek, Guest Lecturer")
        assert game.get_battlefield(game.players[0]).contains(ral)
        assert ral.loyalty == 3

    def test_only_one_loyalty_ability_per_turn(self):
        game, p1, ral = _setup()
        _activate_loyalty(game, p1, ral, 0)
        with pytest.raises(AbilityError):
            _activate_loyalty(game, p1, ral, 0)


class TestPlusOneSurveil:
    def test_surveil_two_bin_one_keep_one(self):
        game, p1, ral = _setup()
        _stock_library(game, 0, ["Top Card", "Second Card", "Third Card"])
        p1._script.append(True)   # bin "Top Card"
        p1._script.append(False)  # keep "Second Card"
        _activate_loyalty(game, p1, ral, 0)
        assert ral.loyalty == 4
        graveyard_names = [c.name for c in game.get_graveyard(p1).get_all()]
        assert graveyard_names == ["Top Card"]
        library = game.get_library(p1)
        assert library.top(1)[0].name == "Second Card"


class TestMinusOneDiscards:
    def test_each_target_player_discards(self):
        game, p1, ral = _setup()
        p2 = game.players[1]
        c1 = Creature(name="Mine", base_power=1, base_toughness=1)
        c2 = Creature(name="Theirs", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])
        p1._script.append(c1)  # p1's discard choice
        p2._script.append(c2)  # p2's discard choice
        _activate_loyalty(game, p1, ral, 1, targets=[p1, p2])
        assert ral.loyalty == 2
        assert game.get_graveyard(p1).contains(c1)
        assert game.get_graveyard(p2).contains(c2)

    def test_zero_targets_does_nothing(self):
        game, p1, ral = _setup()
        c1 = Creature(name="Mine", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[c1])
        _activate_loyalty(game, p1, ral, 1, targets=[])
        assert ral.loyalty == 2
        assert game.get_hand(p1).contains(c1)


class TestMinusTwoReanimate:
    def test_returns_cheap_creature_to_battlefield(self):
        game, p1, ral = _setup()
        bear = Creature(name="Cheap Bear", mana_cost=ManaCost.parse("{1}{G}"),
                        base_power=2, base_toughness=2)
        set_board_state(game, 0, graveyard=[bear])
        _activate_loyalty(game, p1, ral, 2, targets=[bear])
        assert ral.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)

    def test_mv_greater_than_three_not_returned(self):
        game, p1, ral = _setup()
        giant = Creature(name="Big Giant", mana_cost=ManaCost.parse("{3}{G}"),
                         base_power=5, base_toughness=5)
        set_board_state(game, 0, graveyard=[giant])
        _activate_loyalty(game, p1, ral, 2, targets=[giant])
        assert game.get_graveyard(p1).contains(giant)
        assert not game.get_battlefield(p1).contains(giant)


class TestMinusSevenUltimate:
    def test_needs_seven_loyalty(self):
        game, p1, ral = _setup()  # loyalty 3
        with pytest.raises(AbilityError):
            _activate_loyalty(game, p1, ral, 3, targets=[game.players[1]])
        assert ral.loyalty == 3

    def test_opponent_skips_heads_turns(self):
        game, p1, ral = _setup(loyalty=7)
        p2 = game.players[1]
        game.rng.seed(12345)
        reference = random.Random(12345)
        expected_heads = sum(reference.randint(0, 1) for _ in range(5))
        _activate_loyalty(game, p1, ral, 3, targets=[p2])
        assert ral.loyalty == 0
        assert p2.skip_turns == expected_heads
        # Rotation: p1 keeps taking turns until the skips are consumed.
        for _ in range(expected_heads):
            start = game.turn_number
            while game.turn_number == start:
                game.advance_phase()
            assert game.active_player is p1
        # After the skips are spent, p2 finally gets a turn.
        start = game.turn_number
        while game.turn_number == start:
            game.advance_phase()
        assert game.active_player is p2
        assert p2.skip_turns == 0
