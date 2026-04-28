"""Turn execution loop for the SilverquiLLM engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

from engine.stack import priority_loop
from engine.types import Phase, Step, Zone


# Steps/phases where priority is given to players.
# In MTG, players do NOT receive priority during Untap and Cleanup (normally).
_NO_PRIORITY_STEPS: set[tuple[Phase, Step | None]] = {
    (Phase.BEGINNING, Step.UNTAP),
    (Phase.ENDING, Step.CLEANUP),
}


def _do_untap_step(game: GameState) -> None:
    """Perform untap step actions: untap all permanents controlled by the active player.

    Per MTG rules, the active player untaps all permanents they control
    during their untap step. Summoning sickness is also cleared at this point.
    """
    active = game.active_player
    bf = active.zones[Zone.BATTLEFIELD]
    for obj in bf.get_all():
        if hasattr(obj, "is_tapped"):
            obj.is_tapped = False
        if hasattr(obj, "summoning_sick"):
            obj.summoning_sick = False

    # Reset land plays for the active player
    active.land_plays_remaining = 1


def _do_draw_step(game: GameState) -> None:
    """Perform draw step actions: active player draws a card.

    In a two-player game, the starting player (the player who takes
    turn 1) skips their draw step on that first turn.  This is per
    MTG comprehensive rules §103.7a.
    """
    # The starting player skips their draw on turn 1.
    if game.turn_number == 1 and game.active_player_index == 0:
        return

    from engine.game import draw_card

    draw_card(game, game.active_player)


def _do_combat_step(game: GameState, step: Step) -> None:
    """Dispatch combat sub-steps to the appropriate combat functions.

    Parameters:
        game: The current game state.
        step: The combat step to execute.
    """
    from engine.combat import (
        combat_damage_step,
        declare_attackers_step,
        declare_blockers_step,
        end_combat_step,
    )

    if step == Step.DECLARE_ATTACKERS:
        declare_attackers_step(game)
    elif step == Step.DECLARE_BLOCKERS:
        declare_blockers_step(game)
    elif step == Step.COMBAT_DAMAGE:
        combat_damage_step(game)
    elif step == Step.END_COMBAT:
        end_combat_step(game)


def _do_cleanup_step(game: GameState) -> None:
    """Perform cleanup step actions.

    - Remove end-of-turn continuous effects.
    - Clear damage marked on all creatures.
    - Discard down to maximum hand size (7) — not yet implemented.
    """
    # Clear damage on all creatures
    for player in game.players:
        bf = player.zones[Zone.BATTLEFIELD]
        for obj in bf.get_all():
            if hasattr(obj, "damage_marked"):
                obj.damage_marked = 0
            if hasattr(obj, "dealt_deathtouch_damage"):
                obj.dealt_deathtouch_damage = False

    # Remove end-of-turn continuous effects
    if hasattr(game, "effect_manager"):
        game.effect_manager.remove_expired(game)


def run_turn(game: GameState) -> None:
    """Execute a full turn, iterating through all phases/steps.

    At each priority point (every phase/step except Untap and Cleanup),
    :func:`priority_loop` is called.  Turn-based actions are performed
    at the appropriate steps:

    - **Untap**: Untap all permanents, clear summoning sickness, reset
      land plays.
    - **Draw**: Active player draws a card.
    - **Combat**: Delegate to combat system functions.
    - **Cleanup**: Clear damage, remove expired effects.

    After the last step (Cleanup), the turn number is incremented and
    the active player swaps via :meth:`GameState.advance_phase`.

    Parameters:
        game: The game state to advance through one complete turn.
    """
    start_turn = game.turn_number

    while game.turn_number == start_turn:
        current = (game.phase, game.step)

        # Perform turn-based actions for the current step
        if current == (Phase.BEGINNING, Step.UNTAP):
            _do_untap_step(game)
        elif current == (Phase.BEGINNING, Step.DRAW):
            _do_draw_step(game)
        elif game.phase == Phase.COMBAT and game.step is not None:
            _do_combat_step(game, game.step)
        elif current == (Phase.ENDING, Step.CLEANUP):
            _do_cleanup_step(game)

        # Grant priority at this phase/step unless it's Untap or Cleanup.
        if current not in _NO_PRIORITY_STEPS:
            priority_loop(game)

        # Advance to the next phase/step (or to next turn).
        game.advance_phase()
