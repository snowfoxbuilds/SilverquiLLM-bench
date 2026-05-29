"""Central game state and turn/phase/step progression."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from engine.combat import CombatState
from engine.continuous_effects import EffectManager
from engine.player import Player
from engine.player import ScriptExhaustedError
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


@dataclass
class DelayedAction:
    """A one-shot delayed effect checked on phase/step transitions."""

    condition: Any
    effect: Any


class GameState:
    """Central game-state object tracking all mutable game information.

    Attributes:
        players: The list of players in the game.
        active_player_index: Index of the current active player.
        priority_player_index: Index of the player who currently has priority.
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
        self.active_player_index: int = 0
        self.priority_player_index: int = 0
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
        self.delayed_actions: list[DelayedAction] = []
        self.coin_flip_history: list[bool] = []
        self.skipped_turns: dict[Player, int] = {}
        self.miracle_windows: dict[Player, Any] = {}

    # ------------------------------------------------------------------
    # Player properties
    # ------------------------------------------------------------------

    @property
    def active_player(self) -> Player:
        """Return the currently active player."""
        return self.players[self.active_player_index]

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
            self.active_player_index = self._determine_next_active_player_index()
            self.priority_player_index = self.active_player_index
            self.phase = _TURN_SEQUENCE[0][0]
            self.step = _TURN_SEQUENCE[0][1]
            for player in self.players:
                player.cards_drawn_this_turn = 0
            self.miracle_windows.clear()

        self.empty_mana_pools()
        self._process_delayed_actions()

    def empty_mana_pools(self) -> None:
        """Empty all players' mana pools — called on each phase/step transition."""
        for player in self.players:
            player.mana_pool.empty()

    def flip_coin(self, player: Player | None = None) -> bool:
        """Flip a coin and return ``True`` for heads, ``False`` for tails."""
        result: bool
        if player is not None:
            try:
                scripted_result = player.choose_yes_no("Coin flip result")
            except (ScriptExhaustedError, NotImplementedError):
                scripted_result = None
            if scripted_result is not None:
                result = bool(scripted_result)
            else:
                result = bool(random.getrandbits(1))
        else:
            result = bool(random.getrandbits(1))
        self.coin_flip_history.append(result)
        return result

    def skip_next_turn(self, player: Player, count: int = 1) -> None:
        """Cause *player* to skip their next *count* turns."""
        if count <= 0:
            return
        self.skipped_turns[player] = self.skipped_turns.get(player, 0) + count

    def get_pending_skipped_turns(self, player: Player) -> int:
        """Return how many upcoming turns *player* will skip."""
        return self.skipped_turns.get(player, 0)

    def _consume_skipped_turn(self, player: Player) -> bool:
        """Consume one pending skipped turn for *player* if present."""
        pending = self.skipped_turns.get(player, 0)
        if pending <= 0:
            return False
        if pending == 1:
            del self.skipped_turns[player]
        else:
            self.skipped_turns[player] = pending - 1
        return True

    def _next_turn_candidate(self) -> int:
        """Return the next player index who would take a turn absent skipping."""
        if self.extra_turns:
            return self.extra_turns.pop(0)

        candidate = self._normal_next_index
        self._normal_next_index = 1 - self._normal_next_index
        return candidate

    def _determine_next_active_player_index(self) -> int:
        """Return the next active player index, consuming skipped turns."""
        while True:
            candidate_index = self._next_turn_candidate()
            candidate_player = self.players[candidate_index]
            if self._consume_skipped_turn(candidate_player):
                continue
            return candidate_index

    def schedule_delayed_action(self, condition: Any, effect: Any) -> None:
        """Register a delayed one-shot effect checked after each transition."""
        self.delayed_actions.append(DelayedAction(condition=condition, effect=effect))

    def _process_delayed_actions(self) -> None:
        """Resolve matching delayed actions and keep the rest queued."""
        remaining: list[DelayedAction] = []
        for delayed_action in self.delayed_actions:
            if delayed_action.condition(self):
                delayed_action.effect(self)
            else:
                remaining.append(delayed_action)
        self.delayed_actions = remaining
