"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random

import pytest

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import AbilityError, LoyaltyAbilityInstance, activate_ability
from engine.card import Creature
from engine.stack import priority_loop
from engine.types import ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _ral_ready(game) -> RalZarekGuestLecturer:
    pw = RalZarekGuestLecturer(owner=None)
    set_board_state(game, 0, battlefield=[pw])
    return pw


def _activate_loyalty(game, pw, index: int, targets=None) -> None:
    """Activate a loyalty ability by printed index through the engine's
    activation pipeline, then resolve it through the priority loop."""
    player = game.players[0]
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    ability = pw.get_loyalty_abilities()[index]
    instance = LoyaltyAbilityInstance(
        source=pw,
        controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        targets=targets or [],
    )
    activate_ability(game, player, instance)
    # Priority passes are consumed before the effect's own prompts.
    game.players[0]._script.appendleft("pass")
    game.players[1]._script.appendleft("pass")
    priority_loop(game)


class TestRalZarekProperties:
    def test_static_data(self) -> None:
        pw = RalZarekGuestLecturer(owner=None)
        assert pw.name == "Ral Zarek, Guest Lecturer"
        assert pw.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3
        assert Supertype.LEGENDARY in pw.supertypes
        assert "Ral" in pw.subtypes


class TestRalZarekPlusOneSurveil:
    def test_surveil_bins_top_keeps_second(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = _ral_ready(game)
        a = Creature(name="A", base_power=1, base_toughness=1)
        b = Creature(name="B", base_power=1, base_toughness=1)
        c = Creature(name="C", base_power=1, base_toughness=1)
        lib = game.get_library(p1)
        for card in (a, b, c):  # c ends on top
            card.owner = p1
            lib.add(card)
        # Surveil prompts top-down: yes to C (bin), no to B (keep).
        p1._script.extend([True, False])
        _activate_loyalty(game, pw, 0)
        assert pw.loyalty == 4
        assert game.get_graveyard(p1).contains(c)
        assert lib.top(1)[0] is b
        assert lib.contains(a)

    def test_surveil_with_empty_library(self) -> None:
        game = create_game()
        pw = _ral_ready(game)
        _activate_loyalty(game, pw, 0)  # no prompts, no crash
        assert pw.loyalty == 4


class TestRalZarekMinusOneDiscard:
    def test_each_target_player_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = _ral_ready(game)
        mine = Creature(name="Mine", base_power=1, base_toughness=1)
        theirs = Creature(name="Theirs", base_power=1, base_toughness=1)
        set_board_state(game, 0, battlefield=[pw], hand=[mine])
        set_board_state(game, 1, hand=[theirs])
        p1._script.append(mine)    # p1's discard choice
        p2._script.append(theirs)  # p2's discard choice
        _activate_loyalty(game, pw, 1, targets=[p1, p2])
        assert pw.loyalty == 2
        assert game.get_graveyard(p1).contains(mine)
        assert game.get_graveyard(p2).contains(theirs)

    def test_zero_target_players(self) -> None:
        game = create_game()
        pw = _ral_ready(game)
        _activate_loyalty(game, pw, 1, targets=[])
        assert pw.loyalty == 2  # cost still paid, nothing else happens


class TestRalZarekMinusTwoReanimate:
    def test_returns_cheap_creature_to_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = _ral_ready(game)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))
        set_board_state(game, 0, battlefield=[pw], graveyard=[bear])
        _activate_loyalty(game, pw, 2, targets=[bear])
        assert pw.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)

    def test_mana_value_four_stays_put(self) -> None:
        game = create_game()
        p1 = game.players[0]
        pw = _ral_ready(game)
        fatty = Creature(name="Fatty", base_power=4, base_toughness=4,
                         mana_cost=ManaCost.parse("{4}"))
        set_board_state(game, 0, battlefield=[pw], graveyard=[fatty])
        _activate_loyalty(game, pw, 2, targets=[fatty])
        assert pw.loyalty == 1  # cost paid; effect checks the target
        assert game.get_graveyard(p1).contains(fatty)
        assert not game.get_battlefield(p1).contains(fatty)


class TestRalZarekUltimate:
    def test_requires_loyalty_seven(self) -> None:
        game = create_game()
        pw = _ral_ready(game)  # loyalty 3
        with pytest.raises(AbilityError):
            _activate_loyalty(game, pw, 3, targets=[game.players[1]])

    def test_opponent_skips_heads_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = _ral_ready(game)
        pw.loyalty = 8
        game.rng = random.Random(0)  # flips 1,1,0,1,1 → 4 heads
        _activate_loyalty(game, pw, 3, targets=[p2])
        assert pw.loyalty == 1
        assert getattr(p2, "skip_turns", 0) == 4
        # Drive the turn rotation: p2's next turns are skipped, so the
        # next active player after p1's turn ends is p1 again.
        from test_utils import advance_to_phase
        from engine.types import Step
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()  # wrap — p2 would be next but skips
        assert game.active_player is p1
        assert p2.skip_turns == 3

    def test_zero_heads_skips_nothing(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = _ral_ready(game)
        pw.loyalty = 8

        class _AllTails(random.Random):
            def randint(self, a, b):
                return 0

        game.rng = _AllTails()
        _activate_loyalty(game, pw, 3, targets=[p2])
        assert getattr(p2, "skip_turns", 0) == 0
