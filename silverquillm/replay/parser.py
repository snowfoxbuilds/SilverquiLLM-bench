"""High-level 17lands replay parser.

Parses raw JSON replay data into a ReplayGame object with full state
reconstruction, action extraction, and card name resolution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from silverquillm.replay.state import (
    ObjectTracker,
    apply_diff,
    apply_full_state,
    extract_object_id_changes,
    infer_actions,
)
from silverquillm.replay.types import (
    GameSnapshot,
    ReplayAction,
    ReplayGame,
    Zone,
)


def load_card_id_map(path: str | Path | None = None) -> dict[int, str]:
    """Load the grpId -> card name mapping.

    Args:
        path: Path to card_id_map.json. If None, uses default location.

    Returns:
        Dict mapping grpId (int) to card name (str).
    """
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "replays" / "card_id_map.json"
    else:
        path = Path(path)

    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    result: dict[int, str] = {}
    grp_to_card = data.get("grpId_to_card", {})
    for grp_id_str, info in grp_to_card.items():
        try:
            result[int(grp_id_str)] = info["card_name"]
        except (ValueError, KeyError):
            continue

    return result


def parse_replay(
    data: dict[str, Any] | str | Path,
    card_id_map: dict[int, str] | None = None,
    card_id_map_path: str | Path | None = None,
) -> ReplayGame:
    """Parse a 17lands replay JSON into a ReplayGame.

    Args:
        data: Either a parsed dict, a JSON string, or a Path to JSON file.
        card_id_map: Pre-loaded grpId->name mapping. If None, loaded from file.
        card_id_map_path: Path to card_id_map.json (used if card_id_map is None).

    Returns:
        A ReplayGame with reconstructed snapshots and inferred actions.
    """
    # Load data
    if isinstance(data, (str, Path)):
        path = Path(data)
        if path.exists():
            with open(path) as f:
                raw = json.load(f)
        else:
            raw = json.loads(str(data))
    else:
        raw = data

    # Load card names
    if card_id_map is None:
        card_id_map = load_card_id_map(card_id_map_path)

    seat_id = raw.get("seat_id", 1)
    opponent_seat_id = raw.get("opponent_seat_id", 2)

    game = ReplayGame(
        seat_id=seat_id,
        opponent_seat_id=opponent_seat_id,
    )

    events = raw.get("events", [])
    tracker = ObjectTracker()

    # Find and process events
    snapshots: list[GameSnapshot] = []
    prev_snapshot: GameSnapshot | None = None

    for event in events:
        gsm = event.get("gameStateMessage")
        if gsm is None:
            continue

        msg_type = gsm.get("type", "")

        if msg_type == "GameStateType_Full":
            snapshot = apply_full_state(gsm)
            # Register all initial objects
            for obj in snapshot.game_objects.values():
                tracker.register(obj.instance_id, obj.grp_id)
            snapshots.append(snapshot)
            prev_snapshot = snapshot

        elif msg_type == "GameStateType_Diff" and prev_snapshot is not None:
            snapshot = apply_diff(prev_snapshot, gsm)

            # Track ObjectIdChanged
            id_changes = extract_object_id_changes(snapshot.annotations)
            for orig_id, new_id in id_changes.items():
                new_obj = snapshot.game_objects.get(new_id)
                grp_id = new_obj.grp_id if new_obj else None
                tracker.apply_id_change(orig_id, new_id, grp_id)

            # Register any new objects not yet tracked
            for obj in snapshot.game_objects.values():
                if obj.instance_id not in tracker._id_chain:
                    tracker.register(obj.instance_id, obj.grp_id)

            # Infer actions
            actions = infer_actions(prev_snapshot, snapshot, card_id_map)
            snapshot.actions = actions
            game.actions.extend(actions)

            snapshots.append(snapshot)
            prev_snapshot = snapshot

    game.snapshots = snapshots

    # Extract game info from first snapshot
    if snapshots:
        first = snapshots[0]
        game.game_info = first.game_info
        game.players = dict(first.players)

        # Extract initial library (from first full state)
        for zone in first.zones.values():
            if zone.type == "ZoneType_Library":
                grp_ids = []
                for iid in zone.object_instance_ids:
                    obj = first.game_objects.get(iid)
                    if obj:
                        grp_ids.append(obj.grp_id)
                if zone.owner_seat_id:
                    game.initial_library[zone.owner_seat_id] = grp_ids

    # Determine game result from final snapshot
    if snapshots:
        final = snapshots[-1]
        if final.game_info.stage == "GameStage_GameOver":
            # Check player statuses
            for seat, player in final.players.items():
                if player.status == "PlayerStatus_Wins":
                    if seat == seat_id:
                        game.result = "win"
                    else:
                        game.result = "loss"
                    break
            if not game.result and final.game_info.match_state in (
                "MatchState_GameComplete",
                "MatchState_MatchComplete",
            ):
                game.result = "loss"  # default

    return game
