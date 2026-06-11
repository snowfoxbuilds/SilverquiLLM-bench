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
from engine.casting import resolve_top
from engine.types import ManaCost, Phase, Zone
from test_utils import create_game, set_board_state


def _setup(game):
    clear_loyalty_tracking()
    p1 = game.players[0]
    pw = RalZarekGuestLecturer(owner=p1)
    set_board_state(game, 0, battlefield=[pw])
    pw.register_triggers(game)
    # Sorcery-speed timing for loyalty activation.
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    return pw


def _activate(game, pw, index, targets=None):
    """Activate a printed loyalty ability by index through the engine."""
    ability = pw.get_loyalty_abilities()[index]
    instance = LoyaltyAbilityInstance(
        source=pw,
        controller=pw.controller,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        targets=targets,
    )
    activate_ability(game, pw.controller, instance)
    resolve_top(game)


def _stock_library(player, cards):
    library = player.zones[Zone.LIBRARY]
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


class TestSurveil:
    def test_plus1_surveils_two(self):
        """Top card binned, second kept on top; loyalty 3 → 4."""
        game = create_game()
        p1 = game.players[0]
        pw = _setup(game)
        keep = Instant(name="Keep", mana_cost=ManaCost.parse("{1}"))
        bin_ = Instant(name="Bin", mana_cost=ManaCost.parse("{1}"))
        _stock_library(p1, [keep, bin_])  # "Bin" ends up on top

        p1._script.extend([True, False])  # bin the top, keep the next
        _activate(game, pw, 0)

        assert pw.loyalty == 4
        assert p1.zones[Zone.GRAVEYARD].contains(bin_)
        library = p1.zones[Zone.LIBRARY]
        assert library.top(1) == [keep]

    def test_plus1_with_empty_library(self):
        game = create_game()
        pw = _setup(game)
        _activate(game, pw, 0)  # no prompts, no crash
        assert pw.loyalty == 4


class TestDiscard:
    def test_minus1_each_target_player_discards(self):
        game = create_game()
        p1, p2 = game.players
        pw = _setup(game)
        c1 = Instant(name="C1", mana_cost=ManaCost.parse("{1}"))
        c2 = Instant(name="C2", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[c1])
        set_board_state(game, 1, hand=[c2])
        p1._script.append(c1)
        p2._script.append(c2)

        _activate(game, pw, 1, targets=[p1, p2])

        assert pw.loyalty == 2
        assert p1.zones[Zone.GRAVEYARD].contains(c1)
        assert p2.zones[Zone.GRAVEYARD].contains(c2)

    def test_minus1_zero_targets(self):
        game = create_game()
        pw = _setup(game)
        _activate(game, pw, 1, targets=[])
        assert pw.loyalty == 2


class TestReanimate:
    def test_minus2_returns_cheap_creature(self):
        game = create_game()
        p1 = game.players[0]
        pw = _setup(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, graveyard=[bear])

        _activate(game, pw, 2, targets=[bear])

        assert pw.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_minus2_mv_above_three_stays(self):
        game = create_game()
        p1 = game.players[0]
        pw = _setup(game)
        ogre = Creature(name="Ogre", base_power=4, base_toughness=4,
                        mana_cost=ManaCost.parse("{3}{R}"))
        set_board_state(game, 0, graveyard=[ogre])

        _activate(game, pw, 2, targets=[ogre])

        assert pw.loyalty == 1  # cost still paid; effect fizzles
        assert p1.zones[Zone.GRAVEYARD].contains(ogre)


class TestUltimate:
    def test_minus7_two_heads_skips_two_turns(self):
        game = create_game()
        p1, p2 = game.players
        pw = _setup(game)
        pw.loyalty = 7
        game.rng = random.Random(1)  # flips to exactly 2 heads

        _activate(game, pw, 3, targets=[p2])

        assert pw.loyalty == 0
        assert p2.skip_turns == 2

        # Turn rotation: p2's next two turns are skipped.
        from engine.types import Step

        from test_utils import advance_to_phase

        assert game.active_player is p1  # turn 1
        for expected in (p1, p1, p2):  # turns 2, 3 are p1's; then p2 plays
            advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
            game.advance_phase()
            assert game.active_player is expected
        assert p2.skip_turns == 0

    def test_minus7_zero_heads_skips_nothing(self):
        game = create_game()
        p2 = game.players[1]
        pw = _setup(game)
        pw.loyalty = 7
        game.rng = random.Random(15)  # flips to 0 heads

        _activate(game, pw, 3, targets=[p2])
        assert p2.skip_turns == 0

    def test_minus7_requires_seven_loyalty(self):
        game = create_game()
        p2 = game.players[1]
        pw = _setup(game)  # loyalty 3
        with pytest.raises(AbilityError):
            _activate(game, pw, 3, targets=[p2])
        assert pw.loyalty == 3


class TestActivationRules:
    def test_once_per_turn(self):
        game = create_game()
        pw = _setup(game)
        _activate(game, pw, 0)
        with pytest.raises(AbilityError):
            _activate(game, pw, 0)

    def test_starting_loyalty(self):
        pw = RalZarekGuestLecturer()
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3
