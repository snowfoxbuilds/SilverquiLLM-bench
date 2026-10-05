"""Central game state and turn/phase/step progression."""

from __future__ import annotations

import enum
from dataclasses import dataclass

from typing import Any

from engine.combat import CombatState
from engine.continuous_effects import EffectManager
from engine.player import Player
from engine.refs_registry import GameRefsRegistry
from engine.replacement_effects import ReplacementManager
from engine.stack import Stack
from engine.triggers import TriggerManager
from engine.types import Phase, Step, Zone
from engine.zones import ZoneContainer

# Ordered list of (Phase, Step | None) representing a full MTG turn.
_TURN_SEQUENCE: list[tuple[Phase, Step | None]] = [
    # Beginning phase
    (Phase.BEGINNING, Step.UNTAP),
    (Phase.BEGINNING, Step.UPKEEP),
    (Phase.BEGINNING, Step.DRAW),
    # Precombat main phase
    (Phase.PRECOMBAT_MAIN, None),
    # Combat phase
    (Phase.COMBAT, Step.BEGIN_COMBAT),
    (Phase.COMBAT, Step.DECLARE_ATTACKERS),
    (Phase.COMBAT, Step.DECLARE_BLOCKERS),
    (Phase.COMBAT, Step.COMBAT_DAMAGE),
    (Phase.COMBAT, Step.END_COMBAT),
    # Postcombat main phase
    (Phase.POSTCOMBAT_MAIN, None),
    # Ending phase
    (Phase.ENDING, Step.END),
    (Phase.ENDING, Step.CLEANUP),
]



class StepState(enum.Enum):
    """Where the current step is in its lifecycle.

    Only the engine's one stepping entry, :func:`engine.turn.advance`,
    moves this state on, whichever driver calls it, so none keeps lifecycle
    bookkeeping of its own.
    """

    # The step's turn-based actions are still to come — in cleanup, its next
    # cleanup iteration (rule 514.3a).
    PENDING = "pending"
    # The step's priority window is open.
    WINDOW = "window"
    # The step is complete; the game moves to the next one.
    DONE = "done"


@dataclass
class PriorityWindow:
    """A step's open priority window and the priority round it holds.

    Only the rules change the round (CR 117.3–117.4): the window opens with the
    active player holding priority, a player who acts receives priority again,
    a pass moves priority to the next player, and a resolution returns it to
    the active player. Every player passing in succession resolves the top
    object or, on an empty stack, ends the step.
    """

    holder: int
    passes: int = 0

    def acted(self) -> None:
        self.passes = 0

    def passed(self, players: int) -> None:
        self.passes += 1
        self.holder = (self.holder + 1) % players

    def resolved(self, active: int) -> None:
        self.holder, self.passes = active, 0

    def all_passed(self, players: int) -> bool:
        return self.passes >= players

class GameState:
    """Central game-state object tracking all mutable game information.

    Attributes:
        players: The list of players in the game.
        active_player_index: Index of the current active player.
        priority_player_index: Index of the player who holds priority in the
            open window (the active player when no window is open).
        phase: Current phase of the turn.
        step: Current step within the phase (``None`` for main phases).
        turn_number: The current turn number (1-indexed).
        stack: The game stack for spells and abilities.
        trigger_manager: Central registry for triggered abilities.
        replacement_manager: Central registry for replacement effects.
        effect_manager: Manager for continuous effects and the layer system.
        is_game_over: Whether the game has ended.
        winner: The winning player, or ``None`` if the game is ongoing / draw.
    """

    def __init__(self, players: list[Player]) -> None:
        if len(players) < 2:
            raise ValueError("GameState requires at least 2 players")
        if len(players) > 2:
            raise ValueError("GameState supports exactly 2 players")

        self.players: list[Player] = players
        # Game Refs registry: engine-owned instance-id minting + the
        # decision↔object correlation used to map a raised query's options back
        # to game objects when the player answers.
        self.refs: GameRefsRegistry = GameRefsRegistry()
        for seat, player in enumerate(players):
            self.refs.register_player(player, seat)
        self.active_player_index: int = 0
        # Where the current step is in its lifecycle (see StepState), and its
        # open priority window, which holds the priority round.
        self.step_state: StepState = StepState.PENDING
        self.window: PriorityWindow | None = None
        self.phase: Phase = Phase.BEGINNING
        self.step: Step | None = Step.UNTAP
        self.turn_number: int = 1
        self.stack: Stack = Stack()
        self.trigger_manager: TriggerManager = TriggerManager()
        self.replacement_manager: ReplacementManager = ReplacementManager()
        self.effect_manager: EffectManager = EffectManager()
        self.combat_state: CombatState = CombatState()
        self.is_game_over: bool = False
        self.winner: Player | None = None
        # ENGINE LIMITATION: Extra turns queue (FIFO of player seat indices).
        # Complex interactions ('skip your next turn', multiple extra turns
        # from different sources) are not fully handled.
        self.extra_turns: list[int] = []
        # Tracks normal turn rotation independently of extra turns.
        # Extra turns are truly *inserted* — they don't advance the
        # normal rotation.  When extras are exhausted the game picks up
        # from _normal_next_index.
        self._normal_next_index: int = 1

    # ------------------------------------------------------------------
    # Player properties
    # ------------------------------------------------------------------

    @property
    def active_player(self) -> Player:
        """Return the currently active player."""
        return self.players[self.active_player_index]

    @property
    def priority_player_index(self) -> int:
        """The seat holding priority in the open window; the active player's
        when no window is open."""
        return self.window.holder if self.window is not None else self.active_player_index

    @priority_player_index.setter
    def priority_player_index(self, seat: int) -> None:
        # Setup only, for tests that act out of turn: priority is held only in
        # an open window, so with none open there is nothing to hand over.
        if self.window is not None:
            self.window.holder = seat

    @property
    def priority_player(self) -> Player:
        """Return the player who currently has priority."""
        return self.players[self.priority_player_index]

    @property
    def non_active_player(self) -> Player:
        """Return the non-active player (2-player assumption for v1)."""
        return self.players[1 - self.active_player_index]

    # ------------------------------------------------------------------
    # Zone accessors
    # ------------------------------------------------------------------

    def get_battlefield(self, player: Player) -> ZoneContainer:
        """Return the battlefield zone for *player*."""
        return player.zones[Zone.BATTLEFIELD]

    def get_hand(self, player: Player) -> ZoneContainer:
        """Return the hand zone for *player*."""
        return player.zones[Zone.HAND]

    def get_graveyard(self, player: Player) -> ZoneContainer:
        """Return the graveyard zone for *player*."""
        return player.zones[Zone.GRAVEYARD]

    def get_library(self, player: Player) -> ZoneContainer:
        """Return the library zone for *player*."""
        return player.zones[Zone.LIBRARY]

    def get_exile(self, player: Player) -> ZoneContainer:
        """Return the exile zone for *player*."""
        return player.zones[Zone.EXILE]

    # ------------------------------------------------------------------
    # Phase/step progression
    # ------------------------------------------------------------------

    def advance_phase(self) -> None:
        """Advance to the next phase/step in MTG turn order.

        At the end of CLEANUP, the turn number is incremented and the
        active player swaps (2-player assumption).  Mana pools are
        emptied on every transition.
        """
        self.close_window(StepState.PENDING)
        current = (self.phase, self.step)
        idx = _TURN_SEQUENCE.index(current)

        if idx + 1 < len(_TURN_SEQUENCE):
            # Move to next phase/step within the same turn.
            next_phase, next_step = _TURN_SEQUENCE[idx + 1]
            self.phase = next_phase
            self.step = next_step
        else:
            # End of turn — wrap around.
            self.turn_number += 1
            if self.extra_turns:
                # ENGINE LIMITATION: Extra turns queue (FIFO). Pop the
                # next player seat index; that player gets the next turn.
                # Normal rotation is NOT advanced — extra turns are
                # inserted before the normal next turn.
                self.active_player_index = self.extra_turns.pop(0)
            else:
                self.active_player_index = self._normal_next_index
                self._normal_next_index = 1 - self._normal_next_index
            self.phase = _TURN_SEQUENCE[0][0]
            self.step = _TURN_SEQUENCE[0][1]

            # The active player has changed. Re-derive continuous effects so a
            # turn-dependent buff ("during your turn ...", e.g. Quick-Draw
            # Katana) is recalculated at the actual turn transition — not only
            # during the ending turn's cleanup, which still saw the old active
            # player. apply_all is idempotent (reset-then-reapply).
            effect_manager = getattr(self, "effect_manager", None)
            if effect_manager is not None and len(effect_manager) > 0:
                effect_manager.apply_all(self)

        self.empty_mana_pools()

    def open_window(self) -> None:
        """Open the current step's priority window, the active player holding
        priority (rule 117.3a)."""
        self.step_state = StepState.WINDOW
        self.window = PriorityWindow(self.active_player_index)

    def close_window(self, state: StepState) -> None:
        """Close any open window, leaving the step ``state``."""
        self.step_state = state
        self.window = None

    def empty_mana_pools(self) -> None:
        """Empty all players' mana pools — called on each phase/step transition."""
        for player in self.players:
            player.mana_pool.empty()
