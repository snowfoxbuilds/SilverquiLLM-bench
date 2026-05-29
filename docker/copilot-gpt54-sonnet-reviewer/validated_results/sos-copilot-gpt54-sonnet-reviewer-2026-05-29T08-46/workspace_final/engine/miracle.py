"""Miracle metadata lookup and draw-time casting support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.card import MiracleMetadata

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


@dataclass
class MiracleWindow:
    """Tracks the current miracle reveal/cast window for a player."""

    player: Player
    card: Any
    cost: Any
    source: Any
    turn_number: int
    revealed: bool = False


def get_miracle_metadata(game: GameState, card: Any) -> MiracleMetadata | None:
    """Return the current miracle metadata for *card*."""
    printed_cost = getattr(card, "miracle_cost", None)
    if printed_cost is not None:
        return MiracleMetadata(cost=printed_cost, source=card, granted=False)

    hand_player = None
    for player in game.players:
        if game.get_hand(player).contains(card):
            hand_player = player
            break
    if hand_player is None:
        return None

    for permanent in game.get_battlefield(hand_player).get_all():
        get_granted_miracle_cost = getattr(permanent, "get_granted_miracle_cost", None)
        if get_granted_miracle_cost is None:
            continue
        granted_cost = get_granted_miracle_cost(game, card)
        if granted_cost is None:
            continue
        return MiracleMetadata(cost=granted_cost, source=permanent, granted=True)

    return None


def track_miracle_on_draw(game: GameState, player: Player, card: Any) -> MiracleWindow | None:
    """Open a miracle window when *player* draws their first card of the turn."""
    if getattr(player, "cards_drawn_this_turn", 0) != 1:
        return None

    metadata = get_miracle_metadata(game, card)
    if metadata is None:
        return None

    window = MiracleWindow(
        player=player,
        card=card,
        cost=metadata.cost,
        source=metadata.source,
        turn_number=game.turn_number,
        revealed=False,
    )
    game.miracle_windows[player] = window
    return window


def get_miracle_window(
    game: GameState,
    player: Player,
    card: Any | None = None,
) -> MiracleWindow | None:
    """Return *player*'s current valid miracle window, if any."""
    window = game.miracle_windows.get(player)
    if window is None:
        return None
    if window.turn_number != game.turn_number:
        del game.miracle_windows[player]
        return None
    if card is not None and window.card is not card:
        return None
    if not game.get_hand(player).contains(window.card):
        del game.miracle_windows[player]
        return None
    return window


def reveal_miracle(game: GameState, player: Player, card: Any) -> bool:
    """Reveal *card* for miracle if it is currently eligible."""
    window = get_miracle_window(game, player, card)
    if window is None:
        return False
    window.revealed = True
    return True


def can_cast_via_miracle(game: GameState, player: Player, card: Any) -> bool:
    """Return whether *card* can currently be cast for its miracle cost."""
    window = get_miracle_window(game, player, card)
    if window is None:
        return False
    return window.revealed


def clear_miracle_window(
    game: GameState,
    *,
    player: Player | None = None,
    card: Any | None = None,
) -> None:
    """Clear miracle windows matching *player* and/or *card*."""
    to_remove = []
    for window_player, window in game.miracle_windows.items():
        if player is not None and window_player is not player:
            continue
        if card is not None and window.card is not card:
            continue
        to_remove.append(window_player)
    for window_player in to_remove:
        del game.miracle_windows[window_player]


def clear_all_miracle_windows(game: GameState) -> None:
    """Clear all miracle windows."""
    game.miracle_windows.clear()
