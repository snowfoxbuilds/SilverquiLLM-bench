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
from engine.card import Creature, Instant, Planeswalker
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _activate_loyalty(game, player_index, pw, ability_index, targets=None):
    """Activate a loyalty ability by printed index and resolve via priority."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    if targets is not None:
        pw.chosen_targets = targets
    ability = pw.get_loyalty_abilities()[ability_index]
    activate_ability(game, player, LoyaltyAbilityInstance(
        source=pw,
        controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
    ))
    # Priority passes are consumed before any choices the effect makes.
    for p in game.players:
        p._script.appendleft("pass")
    priority_loop(game)


def _setup():
    game = create_game()
    pw = RalZarekGuestLecturer(owner=None)
    set_board_state(game, 0, battlefield=[pw])
    return game, pw


class TestRalZarekProperties:
    def test_static_data(self) -> None:
        pw = RalZarekGuestLecturer(owner=None)
        assert isinstance(pw, Planeswalker)
        assert pw.name == "Ral Zarek, Guest Lecturer"
        assert pw.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3
        costs = [a.loyalty_cost for a in pw.get_loyalty_abilities()]
        assert costs == [1, -1, -2, -7]


class TestPlusOneSurveil:
    def test_surveil_two_bins_and_keeps(self) -> None:
        game, pw = _setup()
        p0 = game.players[0]
        bottom = Instant(name="Bottom", mana_cost=ManaCost.parse("{U}"))
        second = Instant(name="Second", mana_cost=ManaCost.parse("{U}"))
        top = Instant(name="Top", mana_cost=ManaCost.parse("{U}"))
        for c in (bottom, second, top):
            c.owner = c.controller = p0
            p0.zones[Zone.LIBRARY].add(c)
        # Bin the top card, keep the second.
        p0._script.extend([True, False])
        _activate_loyalty(game, 0, pw, 0)
        assert pw.loyalty == 4
        assert top in p0.zones[Zone.GRAVEYARD].get_all()
        lib = [c.name for c in p0.zones[Zone.LIBRARY].get_all()]
        assert lib == ["Bottom", "Second"]


class TestMinusOneDiscard:
    def test_each_target_player_discards(self) -> None:
        game, pw = _setup()
        p0, p1 = game.players
        mine = Instant(name="Mine", mana_cost=ManaCost.parse("{U}"))
        theirs = Instant(name="Theirs", mana_cost=ManaCost.parse("{R}"))
        set_board_state(game, 0, hand=[mine])
        set_board_state(game, 1, hand=[theirs])
        pw.controller = p0  # set_board_state on hand reassigned nothing for pw
        p0._script.append(mine)
        p1._script.append(theirs)
        _activate_loyalty(game, 0, pw, 1, targets=[p0, p1])
        assert pw.loyalty == 2
        assert mine in p0.zones[Zone.GRAVEYARD].get_all()
        assert theirs in p1.zones[Zone.GRAVEYARD].get_all()

    def test_zero_targets_noop(self) -> None:
        game, pw = _setup()
        _activate_loyalty(game, 0, pw, 1, targets=[])
        assert pw.loyalty == 2


class TestMinusTwoReanimate:
    def test_returns_small_creature_to_battlefield(self) -> None:
        game, pw = _setup()
        p0 = game.players[0]
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, graveyard=[bear])
        pw.controller = p0
        _activate_loyalty(game, 0, pw, 2, targets=[bear])
        assert pw.loyalty == 1
        assert bear in p0.zones[Zone.BATTLEFIELD].get_all()
        assert bear not in p0.zones[Zone.GRAVEYARD].get_all()

    def test_mana_value_above_three_is_illegal(self) -> None:
        game, pw = _setup()
        p0 = game.players[0]
        giant = Creature(name="Giant", base_power=5, base_toughness=5,
                         mana_cost=ManaCost.parse("{3}{G}"))
        set_board_state(game, 0, graveyard=[giant])
        pw.controller = p0
        _activate_loyalty(game, 0, pw, 2, targets=[giant])
        # Loyalty was paid but the target is illegal: stays in graveyard.
        assert giant in p0.zones[Zone.GRAVEYARD].get_all()
        assert giant not in p0.zones[Zone.BATTLEFIELD].get_all()


class TestMinusSevenCoins:
    def _ultimate(self, seed):
        game, pw = _setup()
        pw.loyalty = 8
        game.rng = random.Random(seed)
        p1 = game.players[1]
        _activate_loyalty(game, 0, pw, 3, targets=[p1])
        return game, pw, p1

    def test_requires_loyalty_seven(self) -> None:
        game, pw = _setup()
        assert pw.loyalty == 3
        p1 = game.players[1]
        with pytest.raises(AbilityError):
            _activate_loyalty(game, 0, pw, 3, targets=[p1])
        assert p1.skip_turns == 0

    def test_skips_x_turns_for_x_heads(self) -> None:
        # Find a seed with a known number of heads, deterministically.
        seed = 7
        reference = random.Random(seed)
        expected = sum(reference.randint(0, 1) for _ in range(5))
        game, pw, p1 = self._ultimate(seed)
        assert pw.loyalty == 1
        assert p1.skip_turns == expected

    def test_skipped_player_misses_their_turns(self) -> None:
        game, pw = _setup()
        p0, p1 = game.players
        p1.skip_turns = 2
        # Walk three full turns: p1's next two turns are skipped, so the
        # active player stays p0, then p1 finally takes a turn.
        actives = []
        for _ in range(3):
            current_turn = game.turn_number
            while game.turn_number == current_turn:
                game.advance_phase()
            actives.append(game.active_player)
        assert actives == [p0, p0, p1]
        assert p1.skip_turns == 0
