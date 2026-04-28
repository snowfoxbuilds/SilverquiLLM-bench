"""Turn execution loop for the SilverquiLLM engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

from engine.types import Phase, Step


def priority_loop(game: GameState) -> None:
    """Stub priority loop — simply passes for now.

    Will be fleshed out once the Stack is implemented (item 7+).
    """


# Steps/phases where priority is given to players.
# In MTG, players do NOT receive priority during Untap and Cleanup (normally).
_NO_PRIORITY_STEPS: set[tuple[Phase, Step | None]] = {
    (Phase.BEGINNING, Step.UNTAP),
    (Phase.ENDING, Step.CLEANUP),
}


def run_turn(game: GameState) -> None:
    """Execute a full turn, iterating through all phases/steps.

    At each priority point (every phase/step except Untap and Cleanup),
    :func:`priority_loop` is called.  After the last step (Cleanup), the
    turn number is incremented and the active player swaps via
    :meth:`GameState.advance_phase`.

    Parameters:
        game: The game state to advance through one complete turn.
    """
    start_turn = game.turn_number

    while game.turn_number == start_turn:
        # Grant priority at this phase/step unless it's Untap or Cleanup.
        current = (game.phase, game.step)
        if current not in _NO_PRIORITY_STEPS:
            priority_loop(game)

        # Advance to the next phase/step (or to next turn).
        game.advance_phase()
