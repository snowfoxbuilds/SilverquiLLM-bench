"""Turn execution loop for the SilverquiLLM engine."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

from engine.stack import priority_loop
from engine.types import Phase, Step, Zone


# Maximum hand size — players discard down to this during cleanup.
MAX_HAND_SIZE: int = 7


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
    """Perform the cleanup step (MTG rule §514).

    The cleanup step executes the following actions in order:

    1. Active player discards down to maximum hand size (7) using
       :meth:`Player.choose_card`.
    2. Remove all "until end of turn" continuous effects via
       :meth:`EffectManager.remove_expired`, then reapply remaining
       effects for a consistent game state.
    3. Clear damage marked on all creatures on the battlefield.
    4. Clear combat-related flags (``dealt_deathtouch_damage``,
       ``is_attacking``, ``is_blocking``) and reset the combat state.
    5. Empty all players' mana pools.
    6. Check state-based actions.
    7. If triggers fired during cleanup (e.g. from discarding), process
       them (give priority, resolve stack) and perform another cleanup step.
    """
    from engine.game import discard as _discard
    from engine.player import ScriptExhaustedError
    from engine.state_based_actions import resolve_state_based_actions

    # --- Step 1: Discard to hand size ---
    active = game.active_player
    hand = active.zones[Zone.HAND]
    while len(hand) > MAX_HAND_SIZE:
        cards_in_hand = hand.get_all()
        if not cards_in_hand:
            break  # safety guard
        try:
            chosen = active.choose_card(cards_in_hand, "discard to hand size")
        except (ScriptExhaustedError, NotImplementedError) as exc:
            # Player implementation doesn't support choose_card or script
            # was exhausted.  Discard deterministically from end.
            chosen = cards_in_hand[-1]
            exc_name = type(exc).__name__
            warnings.warn(
                f"{exc_name} during cleanup discard for {active.name}; "
                f"auto-discarding {chosen.name}"
            )
        if chosen is not None and hand.contains(chosen):
            _discard(game, active, chosen)
        else:
            # If choose_card returns something invalid, discard the last card
            # to avoid an infinite loop.
            _discard(game, active, cards_in_hand[-1])

    # --- Step 2: Remove "until end of turn" continuous effects ---
    if hasattr(game, "effect_manager"):
        game.effect_manager.remove_expired(game)
        # Reapply remaining effects so the game state is consistent.
        game.effect_manager.apply_all(game)

    # --- Step 3: Clear damage on all creatures ---
    for player in game.players:
        bf = player.zones[Zone.BATTLEFIELD]
        for obj in bf.get_all():
            if hasattr(obj, "damage_marked"):
                obj.damage_marked = 0

    # --- Step 4: Clear combat flags ---
    for player in game.players:
        bf = player.zones[Zone.BATTLEFIELD]
        for obj in bf.get_all():
            if hasattr(obj, "dealt_deathtouch_damage"):
                obj.dealt_deathtouch_damage = False
            if hasattr(obj, "is_attacking"):
                obj.is_attacking = False
            if hasattr(obj, "is_blocking"):
                obj.is_blocking = False
    # Reset the CombatState itself.
    if hasattr(game, "combat_state"):
        game.combat_state.clear()

    # --- Step 5: Empty mana pools ---
    game.empty_mana_pools()

    # --- Step 6: Check state-based actions ---
    sba_happened = resolve_state_based_actions(game)

    # --- Step 7: If SBAs were performed or triggers fired, process & repeat ---
    # Rule 514.3a: if state-based actions were performed or triggered abilities
    # triggered during cleanup, another cleanup step occurs.
    if sba_happened or not game.stack.is_empty():
        # Triggers were placed on the stack — give priority and resolve.
        priority_loop(game)
        # After resolving, perform another cleanup step (recursive).
        _do_cleanup_step(game)


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
        elif current == (Phase.BEGINNING, Step.UPKEEP):
            from engine.events import BeginningOfUpkeepTriggeredEvent
            game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        elif current == (Phase.BEGINNING, Step.DRAW):
            _do_draw_step(game)
        elif current == (Phase.PRECOMBAT_MAIN, None):
            from engine.events import BeginningOfMainPhaseTriggeredEvent
            game.trigger_manager.fire_event(
                game, BeginningOfMainPhaseTriggeredEvent(active_player=game.active_player)
            )
        elif current == (Phase.POSTCOMBAT_MAIN, None):
            from engine.events import BeginningOfMainPhaseTriggeredEvent
            game.trigger_manager.fire_event(
                game, BeginningOfMainPhaseTriggeredEvent(active_player=game.active_player)
            )
        elif game.phase == Phase.COMBAT and game.step is not None:
            _do_combat_step(game, game.step)
        elif current == (Phase.ENDING, Step.CLEANUP):
            _do_cleanup_step(game)

        # Grant priority at this phase/step unless it's Untap or Cleanup.
        if current not in _NO_PRIORITY_STEPS:
            priority_loop(game)

        # Advance to the next phase/step (or to next turn).
        game.advance_phase()
