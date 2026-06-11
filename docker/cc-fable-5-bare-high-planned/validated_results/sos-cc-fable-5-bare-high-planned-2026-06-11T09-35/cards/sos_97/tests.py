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
from engine.card import Creature, Sorcery
from engine.casting import resolve_top
from engine.types import ManaCost, Phase, Zone
from test_utils import create_game, set_board_state


@pytest.fixture(autouse=True)
def _clear_loyalty():
    clear_loyalty_tracking()
    yield
    clear_loyalty_tracking()


def _activate(game, player, pw, index, targets=None):
    """Activate a loyalty ability through the real ability pipeline."""
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    ability = pw.get_loyalty_abilities()[index]
    pw.chosen_targets = targets if targets is not None else []
    activate_ability(game, player, LoyaltyAbilityInstance(
        source=pw, controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        description=ability.description,
    ))
    while not game.stack.is_empty():
        resolve_top(game)


def _fill_library(player, cards):
    library = player.zones[Zone.LIBRARY]
    for c in cards:
        c.owner = player
        c.controller = player
        library.add(c)


def _setup(game, loyalty=None):
    pw = RalZarekGuestLecturer(owner=None)
    set_board_state(game, 0, battlefield=[pw])
    if loyalty is not None:
        pw.loyalty = loyalty
    return pw


class TestRalZarekStatic:
    def test_card_data(self):
        pw = RalZarekGuestLecturer(owner=None)
        assert pw.name == "Ral Zarek, Guest Lecturer"
        assert pw.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert pw.starting_loyalty == 3 and pw.loyalty == 3
        assert len(pw.get_loyalty_abilities()) == 4


class TestPlusOneSurveil:
    def test_surveil_two_bin_one_keep_one(self):
        game = create_game()
        p1 = game.players[0]
        pw = _setup(game)
        a = Sorcery(name="A")
        b = Sorcery(name="B")
        c = Sorcery(name="C")
        _fill_library(p1, [a, b, c])  # c is on top

        # Look at c (top) then b: bin c, keep b.
        p1._script.extend([True, False])
        _activate(game, p1, pw, 0)

        assert pw.loyalty == 4
        assert p1.zones[Zone.GRAVEYARD].contains(c)
        library = p1.zones[Zone.LIBRARY]
        assert library.contains(a) and library.contains(b)
        assert library.top(1)[0] is b, "kept card stays on top"


class TestMinusOneDiscard:
    def test_each_target_player_discards(self):
        game = create_game()
        p1, p2 = game.players
        pw = _setup(game)
        my_card = Sorcery(name="Mine")
        their_card = Sorcery(name="Theirs")
        set_board_state(game, 0, hand=[my_card])
        set_board_state(game, 1, hand=[their_card])

        p1._script.append(my_card)
        p2._script.append(their_card)
        _activate(game, p1, pw, 1, targets=[p1, p2])

        assert pw.loyalty == 2
        assert p1.zones[Zone.GRAVEYARD].contains(my_card)
        assert p2.zones[Zone.GRAVEYARD].contains(their_card)

    def test_zero_targets_discards_nothing(self):
        game = create_game()
        p1, p2 = game.players
        pw = _setup(game)
        their_card = Sorcery(name="Theirs")
        set_board_state(game, 1, hand=[their_card])

        _activate(game, p1, pw, 1, targets=[])

        assert pw.loyalty == 2
        assert p2.zones[Zone.HAND].contains(their_card)


class TestMinusTwoReanimate:
    def test_returns_small_creature_to_battlefield(self):
        game = create_game()
        p1 = game.players[0]
        pw = _setup(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, graveyard=[bear])

        _activate(game, p1, pw, 2, targets=[bear])

        assert pw.loyalty == 1
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_mv_greater_than_three_stays_put(self):
        game = create_game()
        p1 = game.players[0]
        pw = _setup(game)
        giant = Creature(name="Giant", base_power=5, base_toughness=5,
                         mana_cost=ManaCost.parse("{3}{R}"))
        set_board_state(game, 0, graveyard=[giant])

        _activate(game, p1, pw, 2, targets=[giant])

        assert p1.zones[Zone.GRAVEYARD].contains(giant), "MV 4 is illegal"
        assert not p1.zones[Zone.BATTLEFIELD].contains(giant)


class TestMinusSevenUltimate:
    def test_requires_seven_loyalty(self):
        game = create_game()
        p1, p2 = game.players
        pw = _setup(game)  # loyalty 3
        with pytest.raises(AbilityError):
            _activate(game, p1, pw, 3, targets=[p2])

    def test_coin_flips_set_skip_turns(self):
        game = create_game()
        p1, p2 = game.players
        pw = _setup(game, loyalty=7)
        game.rng = random.Random(7)
        reference_rng = random.Random(7)
        expected_heads = sum(reference_rng.randint(0, 1) for _ in range(5))

        _activate(game, p1, pw, 3, targets=[p2])

        assert pw.loyalty == 0
        assert p2.skip_turns == expected_heads

    def test_opponent_actually_skips_their_turns(self):
        from engine.types import Step
        from test_utils import advance_to_phase

        game = create_game()
        p1, p2 = game.players
        p2.skip_turns = 1

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()  # wrap to next turn

        assert game.active_player is p1, "P2's turn was skipped"
        assert p2.skip_turns == 0, "the skip was consumed"

        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()
        assert game.active_player is p2, "P2 takes their following turn"
