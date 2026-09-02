"""Turn execution loop for the SilverquiLLM engine."""

from __future__ import annotations

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


def untap_step(game: GameState) -> None:
    """Public entry point for the untap step (see :func:`_do_untap_step`)."""
    _do_untap_step(game)


def cleanup_mechanical(game: GameState) -> None:
    """The deterministic core of the cleanup step (rule 514 steps 2-5).

    Expires "until end of turn" continuous effects (and reapplies the
    rest), clears marked damage, deathtouch/combat flags, and per-turn
    trackers (``cards_drawn_this_turn``, ``creature_died_this_turn``),
    resets the combat state, and empties mana pools.

    No discard and no SBA/priority loop — :func:`_do_cleanup_step` wraps
    this with the interactive parts; replay validation runs only this
    mechanical core at GRE turn boundaries (discards there are explicit
    GRE zone moves, and deaths are GRE-observed events).
    """
    if hasattr(game, "effect_manager"):
        game.effect_manager.remove_expired(game)
        # Reapply remaining effects so the game state is consistent.
        game.effect_manager.apply_all(game)

    for player in game.players:
        bf = player.zones[Zone.BATTLEFIELD]
        for obj in bf.get_all():
            if hasattr(obj, "damage_marked"):
                obj.damage_marked = 0
            if hasattr(obj, "dealt_deathtouch_damage"):
                obj.dealt_deathtouch_damage = False
            if hasattr(obj, "is_attacking"):
                obj.is_attacking = False
            if hasattr(obj, "is_blocking"):
                obj.is_blocking = False
        if hasattr(player, "cards_drawn_this_turn"):
            player.cards_drawn_this_turn = 0

    if hasattr(game, "combat_state"):
        game.combat_state.clear()
    if hasattr(game, "creature_died_this_turn"):
        game.creature_died_this_turn = False

    game.empty_mana_pools()


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

    1. Active player discards down to maximum hand size (7) via a
       Player Query (one OBJECT query per discard).
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
    from engine.state_based_actions import resolve_state_based_actions

    # --- Step 1: Discard to hand size (a Player Query) ---
    active = game.active_player
    hand = active.zones[Zone.HAND]
    while len(hand) > MAX_HAND_SIZE:
        cards_in_hand = hand.get_all()
        if not cards_in_hand:
            break  # safety guard
        chosen = _choose_discard(game, active, cards_in_hand)
        if chosen is not None and hand.contains(chosen):
            _discard(game, active, chosen)
        else:
            # Defensive: discard the last card to avoid an infinite loop.
            _discard(game, active, cards_in_hand[-1])

    # --- Steps 2-5: the deterministic core (shared with replay validation) ---
    cleanup_mechanical(game)

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
        elif game.phase == Phase.COMBAT and game.step is not None:
            _do_combat_step(game, game.step)
        elif current == (Phase.ENDING, Step.CLEANUP):
            _do_cleanup_step(game)

        # Grant priority at this phase/step unless it's Untap or Cleanup.
        if current not in _NO_PRIORITY_STEPS:
            priority_loop(game)

        # Advance to the next phase/step (or to next turn).
        game.advance_phase()


def _choose_discard(game: "GameState", player: object, cards: list) -> object:
    """Raise an OBJECT Player Query for a cleanup discard; map back to the card."""
    from engine.queries import PlayerQuery, ask
    from engine.refs_registry import object_options

    seat = game.refs.seat_of(player)
    options, by_decision = object_options(
        game.refs, ((c, "hand", seat) for c in cards)
    )
    query = PlayerQuery(
        source=(game.refs.player_decision(player, seat=seat),),
        prompt="discard to hand size",
        options=options,
        min=1,
        max=1,
    )
    answer = ask(player, query)
    return by_decision[answer.selected[0]]
