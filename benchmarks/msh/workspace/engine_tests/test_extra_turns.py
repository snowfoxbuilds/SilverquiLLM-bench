"""Tests for extra turns infrastructure (FIFO queue in GameState).

Covers:
- extra_turns attribute initialisation
- Granting an extra turn to the active player (consecutive turns)
- Normal turn order resumes after the extra turn is consumed
- Multiple extra turns queued in FIFO order
- Extra turns for different players interleave correctly
- Adding an extra turn *during* an extra turn
- Edge cases: empty queue, priority reset, turn number increments
"""

from __future__ import annotations

import pytest

from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer
from engine.types import Phase, Step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game() -> GameState:
    """Create a minimal 2-player GameState for extra-turn tests."""
    p0 = DeterministicPlayer("Alice")
    p1 = DeterministicPlayer("Bob")
    for p in (p0, p1):
        p.life = 20
    return GameState([p0, p1])


def _end_turn(game: GameState) -> None:
    """Fast-forward to CLEANUP and advance, simulating end-of-turn."""
    game.phase = Phase.ENDING
    game.step = Step.CLEANUP
    game.advance_phase()


# ---------------------------------------------------------------------------
# Attribute initialisation
# ---------------------------------------------------------------------------


class TestExtraTurnsAttribute:
    """GameState.extra_turns should be an empty list by default."""

    def test_extra_turns_initialized_empty(self):
        game = _make_game()
        assert game.extra_turns == []

    def test_extra_turns_is_mutable_list(self):
        game = _make_game()
        assert isinstance(game.extra_turns, list)
        # Should be appendable like a normal list
        game.extra_turns.append(0)
        assert len(game.extra_turns) == 1


# ---------------------------------------------------------------------------
# Single extra turn granted
# ---------------------------------------------------------------------------


class TestExtraTurnGranted:
    """Appending a player seat to extra_turns gives them the next turn."""

    def test_active_player_gets_consecutive_turn(self):
        """Player 0 queues an extra turn; they should take turn 2."""
        game = _make_game()
        assert game.active_player_index == 0
        game.extra_turns.append(0)

        _end_turn(game)

        assert game.active_player_index == 0
        assert game.turn_number == 2
        assert game.extra_turns == []

    def test_opponent_gets_extra_turn(self):
        """An effect grants player 1 an extra turn during player 0's turn."""
        game = _make_game()
        game.extra_turns.append(1)

        _end_turn(game)

        assert game.active_player_index == 1
        assert game.turn_number == 2
        assert game.extra_turns == []

    def test_turn_number_increments_on_extra_turn(self):
        """Extra turns still increment the turn counter."""
        game = _make_game()
        game.extra_turns.append(0)

        _end_turn(game)
        assert game.turn_number == 2

        _end_turn(game)
        assert game.turn_number == 3


# ---------------------------------------------------------------------------
# Normal turn order resumes after extra turn
# ---------------------------------------------------------------------------


class TestNormalOrderResumes:
    """After extra turns are exhausted, the normal alternation resumes."""

    def test_resumes_to_opponent_after_self_extra_turn(self):
        game = _make_game()
        game.extra_turns.append(0)

        _end_turn(game)  # turn 2: extra for P0
        assert game.active_player_index == 0

        _end_turn(game)  # turn 3: normal -> P1
        assert game.active_player_index == 1

    def test_resumes_after_opponent_extra_turn(self):
        """After P1 takes an inserted extra turn, normal rotation resumes
        from where it left off — P0 was the last *normal* active player,
        so the next normal turn belongs to P1 (P0 → P1(extra) → P1(normal))."""
        game = _make_game()
        game.extra_turns.append(1)

        _end_turn(game)  # turn 2: extra for P1
        assert game.active_player_index == 1

        _end_turn(game)  # turn 3: normal rotation from P0 → P1
        assert game.active_player_index == 1

    def test_empty_queue_normal_alternation(self):
        """With no extra turns queued, turns alternate normally."""
        game = _make_game()

        _end_turn(game)
        assert game.active_player_index == 1

        _end_turn(game)
        assert game.active_player_index == 0


# ---------------------------------------------------------------------------
# Multiple extra turns — FIFO ordering
# ---------------------------------------------------------------------------


class TestMultipleExtraTurnsFIFO:
    """Multiple extra turns must be processed first-in, first-out."""

    def test_two_extra_turns_same_player(self):
        game = _make_game()
        game.extra_turns.extend([0, 0])

        _end_turn(game)
        assert game.active_player_index == 0
        assert len(game.extra_turns) == 1

        _end_turn(game)
        assert game.active_player_index == 0
        assert game.extra_turns == []

        _end_turn(game)  # normal: -> P1
        assert game.active_player_index == 1

    def test_fifo_different_players(self):
        """Queue [P0, P1] — P0's extra first, then P1's extra."""
        game = _make_game()
        game.extra_turns.extend([0, 1])

        _end_turn(game)
        assert game.active_player_index == 0

        _end_turn(game)
        assert game.active_player_index == 1

    def test_three_extras_interleaved(self):
        """Queue [P0, P1, P0] — should pop in that exact order."""
        game = _make_game()
        game.extra_turns.extend([0, 1, 0])

        results = []
        for _ in range(3):
            _end_turn(game)
            results.append(game.active_player_index)

        assert results == [0, 1, 0]
        assert game.extra_turns == []

    def test_normal_order_resumes_after_all_extras_consumed(self):
        """After [P0, P1] extras, normal alternation resumes from the last
        *normal* turn (P0), so next normal turn is P1."""
        game = _make_game()
        game.extra_turns.extend([0, 1])

        _end_turn(game)  # extra P0
        _end_turn(game)  # extra P1

        _end_turn(game)  # normal: P0 was last normal → P1
        assert game.active_player_index == 1


# ---------------------------------------------------------------------------
# Extra turn during an extra turn
# ---------------------------------------------------------------------------


class TestExtraTurnDuringExtraTurn:
    """Queueing an extra turn while taking an extra turn should work."""

    def test_queue_extra_during_extra(self):
        """P0 gets an extra turn, then during that extra turn queues another."""
        game = _make_game()
        game.extra_turns.append(0)

        _end_turn(game)  # extra turn for P0
        assert game.active_player_index == 0

        # During the extra turn, another extra turn is granted
        game.extra_turns.append(0)

        _end_turn(game)  # second extra for P0
        assert game.active_player_index == 0

        _end_turn(game)  # normal -> P1
        assert game.active_player_index == 1

    def test_queue_opponent_extra_during_own_extra(self):
        """P0 takes extra turn, queues extra for P1 during it.
        Normal rotation still tracks P0 as last normal, so after
        extras: P0(extra) → P1(extra) → P1(normal)."""
        game = _make_game()
        game.extra_turns.append(0)

        _end_turn(game)
        assert game.active_player_index == 0

        game.extra_turns.append(1)

        _end_turn(game)
        assert game.active_player_index == 1

        _end_turn(game)  # normal: P0 was last normal → P1
        assert game.active_player_index == 1


# ---------------------------------------------------------------------------
# Priority and phase reset on extra turn
# ---------------------------------------------------------------------------


class TestPriorityAndPhaseReset:
    """On a new turn (including extra), priority and phase should reset."""

    def test_priority_set_to_active_player_on_extra_turn(self):
        game = _make_game()
        game.extra_turns.append(0)
        game.priority_player_index = 1  # opponent had priority

        _end_turn(game)

        assert game.priority_player_index == 0

    def test_phase_resets_to_beginning_on_extra_turn(self):
        game = _make_game()
        game.extra_turns.append(0)

        _end_turn(game)

        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UNTAP
