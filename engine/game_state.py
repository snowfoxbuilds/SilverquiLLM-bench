"""Central game state and turn/phase/step progression."""

from __future__ import annotations

from typing import Any

from engine.player import Player
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
        self.is_game_over: bool = False
        self.winner: Player | None = None

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
            self.active_player_index = 1 - self.active_player_index
            self.priority_player_index = self.active_player_index
            self.phase = _TURN_SEQUENCE[0][0]
            self.step = _TURN_SEQUENCE[0][1]

        self.empty_mana_pools()

    def empty_mana_pools(self) -> None:
        """Empty all players' mana pools — called on each phase/step transition."""
        for player in self.players:
            player.mana_pool.empty()
