"""Central game state and turn/phase/step progression."""

from __future__ import annotations

import random
from typing import Any

from engine.combat import CombatState
from engine.continuous_effects import EffectManager
from engine.player import Player
from engine.replacement_effects import ReplacementManager
from engine.stack import Stack
from engine.triggers import TriggerManager
from engine.types import Color
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
        self._current_turn_is_extra: bool = False
        # Delayed effects that should occur at the beginning of a player's
        # next main phase. Each item is ``{"player": Player, "callback": fn}``.
        self._next_main_phase_callbacks: list[dict[str, Any]] = []
        self.coin_flip_results: list[bool] = []
        self._skipped_turns: dict[int, int] = {}
        self._temporary_play_permissions: list[dict[str, Any]] = []
        self._player_turn_counts: dict[int, int] = {
            index: (1 if index == self.active_player_index else 0)
            for index in range(len(players))
        }

    def update_game_over(self) -> None:
        """Refresh ``is_game_over`` / ``winner`` from current loss markers."""
        lost_players = [p for p in self.players if p.has_lost]

        if len(lost_players) == len(self.players):
            self.is_game_over = True
            self.winner = None
            return

        if len(lost_players) == 1:
            self.is_game_over = True
            self.winner = [p for p in self.players if not p.has_lost][0]
            return

        self.is_game_over = False
        self.winner = None

    def get_player_colors(self, player: Player) -> set[Color]:
        """Return normalized colors for *player* from any public color marker."""
        raw_colors = getattr(player, "colors", None)
        if raw_colors is None:
            raw_color = getattr(player, "color", None)
            raw_colors = [] if raw_color is None else [raw_color]
        if raw_colors is None:
            raw_colors = []

        normalized: set[Color] = set()
        for color in raw_colors:
            if isinstance(color, Color):
                normalized.add(color)
                continue
            color_name = getattr(color, "name", None)
            if color_name in Color.__members__:
                normalized.add(Color[color_name])
                continue
            color_value = getattr(color, "value", color)
            if isinstance(color_value, str):
                upper = color_value.upper()
                for candidate in Color:
                    if upper in {candidate.name, candidate.value}:
                        normalized.add(candidate)
                        break
        return normalized

    def is_monocolored_player(self, player: Player) -> bool:
        """Return ``True`` when *player* has exactly one color."""
        return len(self.get_player_colors(player)) == 1

    def get_monocolored_players(self, players: list[Player] | None = None) -> list[Player]:
        """Return the monocolored players from *players* or all players."""
        candidate_players = self.players if players is None else players
        return [player for player in candidate_players if self.is_monocolored_player(player)]

    def choose_monocolored_player(
        self,
        chooser: Player,
        players: list[Player] | None = None,
        description: str = "Choose a monocolored player",
    ) -> Player | None:
        """Deterministically choose among monocolored players, or ``None`` if none exist."""
        legal_players = self.get_monocolored_players(players)
        if not legal_players:
            return None
        chosen = chooser.choose_target(
            legal_players,
            {"description": description, "filter_fn": lambda player: player in legal_players},
        )
        if chosen not in legal_players:
            raise ValueError("Chosen player is not a legal monocolored player")
        return chosen

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
            if self.extra_turns:
                # ENGINE LIMITATION: Extra turns queue (FIFO). Pop the
                # next player seat index; that player gets the next turn.
                # Normal rotation is NOT advanced — extra turns are
                # inserted before the normal next turn.
                self.active_player_index = self.extra_turns.pop(0)
                self._current_turn_is_extra = True
            else:
                expected_previous = 1 - self._normal_next_index
                if self._current_turn_is_extra:
                    self.active_player_index = self._normal_next_index
                    self._normal_next_index = 1 - self._normal_next_index
                elif self.active_player_index != expected_previous:
                    self.active_player_index = 1 - self.active_player_index
                    self._normal_next_index = 1 - self.active_player_index
                else:
                    self.active_player_index = self._normal_next_index
                    self._normal_next_index = 1 - self._normal_next_index
                self._current_turn_is_extra = False
            self.active_player_index = self._apply_turn_skips(self.active_player_index)
            self.priority_player_index = self.active_player_index
            self.phase = _TURN_SEQUENCE[0][0]
            self.step = _TURN_SEQUENCE[0][1]
            self._player_turn_counts[self.active_player_index] = (
                self._player_turn_counts.get(self.active_player_index, 0) + 1
            )
            self._remove_expired_temporary_play_permissions()

        self.empty_mana_pools()
        if self.phase == Phase.PRECOMBAT_MAIN and self.step is None:
            from engine.events import BeginningOfFirstMainPhaseTriggeredEvent

            self.trigger_manager.fire_event(
                self,
                BeginningOfFirstMainPhaseTriggeredEvent(player=self.active_player),
            )
        self._process_next_main_phase_callbacks()

    def empty_mana_pools(self) -> None:
        """Empty all players' mana pools — called on each phase/step transition."""
        for player in self.players:
            player.mana_pool.empty()

    def schedule_for_next_main_phase(self, player: Player, callback: Any) -> None:
        """Schedule *callback* for the beginning of *player*'s next main phase."""
        self._next_main_phase_callbacks.append({
            "player": player,
            "callback": callback,
        })

    def set_coin_flip_results(self, results: list[bool]) -> None:
        """Seed deterministic coin-flip results for tests."""
        self.coin_flip_results = list(results)

    def flip_coin(self) -> bool:
        """Return a deterministic or random coin-flip result.

        ``True`` represents heads and ``False`` represents tails.
        """
        if self.coin_flip_results:
            return self.coin_flip_results.pop(0)
        return bool(random.getrandbits(1))

    def skip_next_turn(self, player: Player | int) -> None:
        """Cause *player* to skip their next turn."""
        self.skip_next_turns(player, 1)

    def skip_next_turns(self, player: Player | int, count: int) -> None:
        """Cause *player* to skip their next *count* turns."""
        if count <= 0:
            return
        player_index = self._player_index(player)
        self._skipped_turns[player_index] = self._skipped_turns.get(player_index, 0) + count

    def remaining_skipped_turns(self, player: Player | int) -> int:
        """Return how many upcoming turns *player* will skip."""
        return self._skipped_turns.get(self._player_index(player), 0)

    def grant_temporary_play_permission(
        self,
        card: Any,
        player: Player | int,
        *,
        duration: str = "this_turn",
    ) -> None:
        """Public API: allow *player* to play *card* for a temporary window.

        Supported durations:
        - ``"this_turn"``: until the current turn ends.
        - ``"next_turn_of_player"``: until the end of that player's next turn.
        """
        player_index = self._player_index(player)
        permission: dict[str, Any] = {
            "card": card,
            "player_index": player_index,
        }
        if duration == "this_turn":
            permission["expires_turn_number"] = self.turn_number
        elif duration == "next_turn_of_player":
            permission["expires_player_index"] = player_index
            permission["expires_player_turn_count"] = self._player_turn_counts.get(player_index, 0) + 1
        else:
            raise ValueError(f"Unsupported play-permission duration: {duration!r}")

        self.clear_temporary_play_permissions_for_card(card, player=player_index)
        self._temporary_play_permissions.append(permission)

    def can_player_temporarily_play_card(self, player: Player | int, card: Any) -> bool:
        """Return ``True`` if *player* currently has a temporary play permission for *card*."""
        self._remove_expired_temporary_play_permissions()
        player_index = self._player_index(player)
        return any(
            permission.get("card") is card and permission.get("player_index") == player_index
            for permission in self._temporary_play_permissions
        )

    def clear_temporary_play_permissions_for_card(
        self,
        card: Any,
        *,
        player: Player | int | None = None,
    ) -> None:
        """Remove temporary play permissions attached to *card*."""
        if player is None:
            self._temporary_play_permissions = [
                permission
                for permission in self._temporary_play_permissions
                if permission.get("card") is not card
            ]
            return

        player_index = self._player_index(player)
        self._temporary_play_permissions = [
            permission
            for permission in self._temporary_play_permissions
            if not (
                permission.get("card") is card
                and permission.get("player_index") == player_index
            )
        ]

    def _player_index(self, player: Player | int) -> int:
        if isinstance(player, int):
            return player
        return self.players.index(player)

    def _apply_turn_skips(self, candidate_index: int) -> int:
        """Consume pending skip-turn effects and return the next real turn seat."""
        safety = 0
        while self._skipped_turns.get(candidate_index, 0) > 0 and safety < len(self.players) * 8:
            self._skipped_turns[candidate_index] -= 1
            if self._skipped_turns[candidate_index] <= 0:
                del self._skipped_turns[candidate_index]

            if self.extra_turns:
                candidate_index = self.extra_turns.pop(0)
                self._current_turn_is_extra = True
            else:
                candidate_index = 1 - candidate_index
            safety += 1
        return candidate_index

    def _process_next_main_phase_callbacks(self) -> None:
        """Run delayed callbacks waiting for the active player's main phase."""
        if self.step is not None:
            return
        if self.phase not in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN):
            return

        ready: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        for item in self._next_main_phase_callbacks:
            if item.get("player") is self.active_player:
                ready.append(item)
            else:
                pending.append(item)
        self._next_main_phase_callbacks = pending

        for item in ready:
            callback = item.get("callback")
            if callable(callback):
                callback(self)

    def _remove_expired_temporary_play_permissions(self) -> None:
        """Prune play permissions whose turn-based windows have ended."""
        remaining: list[dict[str, Any]] = []
        for permission in self._temporary_play_permissions:
            expires_turn_number = permission.get("expires_turn_number")
            if expires_turn_number is not None and self.turn_number > expires_turn_number:
                continue

            expires_player_index = permission.get("expires_player_index")
            expires_player_turn_count = permission.get("expires_player_turn_count")
            if (
                expires_player_index is not None
                and expires_player_turn_count is not None
                and self._player_turn_counts.get(expires_player_index, 0) > expires_player_turn_count
            ):
                continue

            remaining.append(permission)
        self._temporary_play_permissions = remaining
