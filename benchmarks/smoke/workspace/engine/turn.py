"""Turn execution loop for the SilverquiLLM engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

from engine.game_state import StepState
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
    """Play the cleanup step (MTG rule §514) to completion through the step
    lifecycle (:func:`advance`): cleanup steps until one opens no priority
    window, each that does followed by that window (rule 514.3a).

    It carries on from the game's step state: an open cleanup window is
    played out before the next cleanup step, and a completed cleanup is left
    alone. Called outside cleanup, it moves the game into a fresh cleanup
    step first."""
    if (game.phase, game.step) != (Phase.ENDING, Step.CLEANUP):
        game.phase, game.step = Phase.ENDING, Step.CLEANUP
        game.close_window(StepState.PENDING)
    while game.step_state is not StepState.DONE:
        advance(game)


def cleanup_iteration(game: GameState) -> bool:
    """Perform one cleanup step's actions; return whether players receive
    priority before another cleanup step (rule 514.3a).

    The actions, in order:

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

    Priority is granted only if state-based actions were performed or
    abilities triggered (their triggers are on the stack); the caller then
    gives priority and, once it ends, performs another cleanup step.
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

    return bool(sba_happened) or not game.stack.is_empty()


def run_turn(game: GameState) -> None:
    """Execute the rest of the current turn through the step lifecycle
    (:func:`advance`): each step's turn-based actions once, its priority
    window, and in cleanup the cleanup steps rule 514.3a requires.

    After the last step (Cleanup), the turn number is incremented and the
    active player swaps via :meth:`GameState.advance_phase`. Starting it
    where any other driver stopped carries on from the game's step state, so
    no step's turn-based actions are repeated and a completed step is never
    reopened.

    A game that ends during the turn ends the turn with it.

    Parameters:
        game: The game state to advance through one complete turn.
    """
    start_turn = game.turn_number
    while game.turn_number == start_turn and not game.is_game_over:
        advance(game)


def advance(game: GameState, *, all_pass: bool = False, forced: bool = False) -> None:
    """The engine's one stepping entry: take the game one stage further.

    * A step whose turn-based actions are pending performs them, then opens
      its priority window — or completes, for a step that grants none. In
      cleanup each cleanup step opens a window only when it performed
      state-based actions or put triggers on the stack (rule 514.3a).
    * In an open window the player holding priority acts or passes
      (:func:`engine.priority.take_priority`); once every player has passed
      in succession, the top object resolves or, on an empty stack, the
      window closes and the step is complete — in cleanup, another cleanup
      step follows.
    * A completed step moves the game to the next one — past the declare
      blockers and combat damage steps when nothing attacks (CR 508.8).
    * Once the game is over, nothing happens.

    ``all_pass`` is the priority policy of every player passing without
    being asked; it is not a separate path through the lifecycle.
    ``forced`` is the test helpers' fast-forward: it makes no combat
    declarations, and its draw takes a card from a nonempty library with no
    first-turn exception. Live play never sets it.
    """
    if game.is_game_over:
        return
    if game.step_state is StepState.PENDING:
        _enter_step(game, forced)
    elif game.step_state is StepState.WINDOW:
        _play_priority(game, all_pass)
    else:
        game.advance_phase()
        if game.step is Step.DECLARE_BLOCKERS and not game.combat_state.attackers:
            # CR 508.8: with no attackers, the declare blockers and combat
            # damage steps are skipped.
            game.advance_phase()
            game.advance_phase()


def start_step(game: GameState) -> None:
    """Setup only: begin play in the current step as if its turn-based actions
    were done — open its priority window, or complete it if it grants none."""
    if (game.phase, game.step) in _NO_PRIORITY_STEPS:
        game.close_window(StepState.DONE)
    else:
        game.open_window()


def _play_priority(game: GameState, all_pass: bool) -> None:
    from engine.priority import take_priority
    from engine.stack import resolve_top_of_stack, settle_after_resolution

    window = game.window
    seats = len(game.players)
    if window.all_passed(seats):
        if not game.stack.is_empty():
            resolve_top_of_stack(game)
        else:
            in_cleanup = (game.phase, game.step) == (Phase.ENDING, Step.CLEANUP)
            game.close_window(StepState.PENDING if in_cleanup else StepState.DONE)
        return
    if all_pass:
        # CR 117.5: the game settles before a player receives priority, even
        # when that player's answer is a pass the caller already knows.
        settle_after_resolution(game)
        window.passed(seats)
    elif take_priority(game, game.players[window.holder]):
        window.passed(seats)
    else:
        window.acted()


def _enter_step(game: GameState, forced: bool) -> None:
    current = (game.phase, game.step)
    if current == (Phase.ENDING, Step.CLEANUP):
        if cleanup_iteration(game):
            game.open_window()
        else:
            game.close_window(StepState.DONE)
        return
    _step_actions(game, current, forced)
    if current in _NO_PRIORITY_STEPS:
        game.close_window(StepState.DONE)
    else:
        game.open_window()


def _step_actions(game: GameState, current: tuple, forced: bool) -> None:
    """The turn-based actions and step-entry events of *current*."""
    from engine.events import (
        BeginningOfCombatTriggeredEvent,
        BeginningOfUpkeepTriggeredEvent,
        EndOfTurnTriggeredEvent,
        EndStepTriggeredEvent,
    )

    if current == (Phase.BEGINNING, Step.UNTAP):
        _do_untap_step(game)
    elif current == (Phase.BEGINNING, Step.UPKEEP):
        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
    elif current == (Phase.BEGINNING, Step.DRAW):
        if not forced:
            _do_draw_step(game)
        elif game.get_library(game.active_player).get_all():
            from engine.game import draw_card

            draw_card(game, game.active_player)
    elif current == (Phase.COMBAT, Step.BEGIN_COMBAT):
        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())
    elif game.phase == Phase.COMBAT and game.step is not None:
        if not forced or game.step not in (Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS):
            _do_combat_step(game, game.step)
    elif current == (Phase.ENDING, Step.END):
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=game.active_player))
        game.trigger_manager.fire_event(game, EndOfTurnTriggeredEvent())


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
