"""GRE state reconstruction logic.

Handles merging Full and Diff game state messages into complete snapshots.
"""

from __future__ import annotations

import copy
from typing import Any

from silverquillm.replay.types import (
    Annotation,
    GameInfo,
    GameObject,
    GameSnapshot,
    PlayerInfo,
    ReplayAction,
    TurnInfo,
    Zone,
)


def build_game_info(raw: dict[str, Any]) -> GameInfo:
    """Build GameInfo from raw gameInfo dict."""
    deck_info = raw.get("deckConstraintInfo", {})
    return GameInfo(
        match_id=raw.get("matchID", ""),
        game_number=raw.get("gameNumber", 1),
        stage=raw.get("stage", ""),
        game_type=raw.get("type", ""),
        variant=raw.get("variant", ""),
        match_state=raw.get("matchState", ""),
        match_win_condition=raw.get("matchWinCondition", ""),
        super_format=raw.get("superFormat", ""),
        mulligan_type=raw.get("mulliganType", ""),
        min_deck_size=deck_info.get("minDeckSize", 40),
        max_deck_size=deck_info.get("maxDeckSize", 250),
    )


def build_turn_info(raw: dict[str, Any]) -> TurnInfo:
    """Build TurnInfo from raw turnInfo dict."""
    return TurnInfo(
        phase=raw.get("phase", ""),
        step=raw.get("step", ""),
        turn_number=raw.get("turnNumber", 0),
        active_player=raw.get("activePlayer", 0),
    )


def apply_full_state(gsm: dict[str, Any]) -> GameSnapshot:
    """Create a GameSnapshot from a GameStateType_Full message."""
    game_state_id = gsm.get("gameStateId", 0)

    snapshot = GameSnapshot(game_state_id=game_state_id)

    # gameInfo
    if "gameInfo" in gsm:
        snapshot.game_info = build_game_info(gsm["gameInfo"])

    # players
    for p in gsm.get("players", []):
        seat = p.get("systemSeatNumber", p.get("controllerSeatId", 0))
        snapshot.players[seat] = PlayerInfo(
            seat_id=seat,
            life_total=p.get("lifeTotal", 20),
            status=p.get("status", "PlayerStatus_InGame"),
            max_hand_size=p.get("maxHandSize", 7),
        )

    # turnInfo
    if "turnInfo" in gsm:
        snapshot.turn_info = build_turn_info(gsm["turnInfo"])

    # zones
    for z in gsm.get("zones", []):
        zone = Zone.from_dict(z)
        snapshot.zones[zone.zone_id] = zone

    # gameObjects
    for obj in gsm.get("gameObjects", []):
        go = GameObject.from_dict(obj)
        snapshot.game_objects[go.instance_id] = go

    # annotations (per-state, not cumulative)
    snapshot.annotations = [Annotation.from_dict(a) for a in gsm.get("annotations", [])]

    # persistentAnnotations
    for pa in gsm.get("persistentAnnotations", []):
        ann = Annotation.from_dict(pa)
        snapshot.persistent_annotations[ann.id] = ann

    return snapshot


_GAME_OBJECT_FIELD_MAP: dict[str, str] = {
    "grpId": "grp_id",
    "type": "type",
    "zoneId": "zone_id",
    "ownerSeatId": "owner_seat_id",
    "controllerSeatId": "controller_seat_id",
    "cardTypes": "card_types",
    "superTypes": "super_types",
    "subtypes": "subtypes",
    "color": "color",
    "visibility": "visibility",
    "isTapped": "is_tapped",
    "name": "name",
    "overlayGrpId": "overlay_grp_id",
    "parentId": "parent_id",
    "objectSourceGrpId": "object_source_grp_id",
    "viewers": "viewers",
}


def _merge_game_object(existing: GameObject, diff: dict[str, Any]) -> None:
    """Merge a sparse diff dict onto an existing GameObject in place."""
    for gre_key, attr in _GAME_OBJECT_FIELD_MAP.items():
        if gre_key in diff:
            setattr(existing, attr, diff[gre_key])
    # power/toughness are nested {value: N} dicts
    if "power" in diff:
        p = diff["power"]
        existing.power = p.get("value") if isinstance(p, dict) else None
    if "toughness" in diff:
        t = diff["toughness"]
        existing.toughness = t.get("value") if isinstance(t, dict) else None


def apply_diff(prev: GameSnapshot, gsm: dict[str, Any]) -> GameSnapshot:
    """Apply a GameStateType_Diff to a previous snapshot, returning a new one."""
    game_state_id = gsm.get("gameStateId", 0)

    # Deep copy previous state
    snapshot = GameSnapshot(
        game_state_id=game_state_id,
        turn_info=copy.deepcopy(prev.turn_info),
        players=copy.deepcopy(prev.players),
        zones=copy.deepcopy(prev.zones),
        game_objects=copy.deepcopy(prev.game_objects),
        persistent_annotations=copy.deepcopy(prev.persistent_annotations),
        game_info=copy.deepcopy(prev.game_info),
    )

    # gameInfo — replace if present
    if "gameInfo" in gsm:
        snapshot.game_info = build_game_info(gsm["gameInfo"])

    # players — upsert
    for p in gsm.get("players", []):
        seat = p.get("systemSeatNumber", p.get("controllerSeatId", 0))
        if seat in snapshot.players:
            existing = snapshot.players[seat]
            if "lifeTotal" in p:
                existing.life_total = p["lifeTotal"]
            if "status" in p:
                existing.status = p["status"]
            if "maxHandSize" in p:
                existing.max_hand_size = p["maxHandSize"]
        else:
            snapshot.players[seat] = PlayerInfo(
                seat_id=seat,
                life_total=p.get("lifeTotal", 20),
                status=p.get("status", "PlayerStatus_InGame"),
                max_hand_size=p.get("maxHandSize", 7),
            )

    # turnInfo — merge fields if present (empty {} means no change)
    if "turnInfo" in gsm:
        ti = gsm["turnInfo"]
        if ti:  # non-empty
            if "phase" in ti:
                snapshot.turn_info.phase = ti["phase"]
            if "step" in ti:
                snapshot.turn_info.step = ti["step"]
            if "turnNumber" in ti:
                snapshot.turn_info.turn_number = ti["turnNumber"]
            if "activePlayer" in ti:
                snapshot.turn_info.active_player = ti["activePlayer"]

    # zones — replace by zoneId
    for z in gsm.get("zones", []):
        zone = Zone.from_dict(z)
        # Keep zone type from previous if not in diff (some diffs omit type)
        if not zone.type and zone.zone_id in snapshot.zones:
            zone.type = snapshot.zones[zone.zone_id].type
        if not zone.owner_seat_id and zone.zone_id in snapshot.zones:
            zone.owner_seat_id = snapshot.zones[zone.zone_id].owner_seat_id
        snapshot.zones[zone.zone_id] = zone

    # gameObjects — upsert by instanceId (merge onto existing for diffs)
    for obj in gsm.get("gameObjects", []):
        iid = obj["instanceId"]
        existing = snapshot.game_objects.get(iid)
        if existing is not None:
            # Sparse merge: only update fields present in the diff dict
            _merge_game_object(existing, obj)
        else:
            snapshot.game_objects[iid] = GameObject.from_dict(obj)

    # diffDeletedInstanceIds — remove
    for iid in gsm.get("diffDeletedInstanceIds", []):
        snapshot.game_objects.pop(iid, None)

    # annotations — per-state (not cumulative)
    snapshot.annotations = [Annotation.from_dict(a) for a in gsm.get("annotations", [])]

    # persistentAnnotations — upsert
    for pa in gsm.get("persistentAnnotations", []):
        ann = Annotation.from_dict(pa)
        snapshot.persistent_annotations[ann.id] = ann

    # diffDeletedPersistentAnnotationIds — remove
    for aid in gsm.get("diffDeletedPersistentAnnotationIds", []):
        snapshot.persistent_annotations.pop(aid, None)

    return snapshot


def extract_object_id_changes(annotations: list[Annotation]) -> dict[int, int]:
    """Extract ObjectIdChanged mappings from annotations.

    Returns dict of orig_id -> new_id.
    """
    changes: dict[int, int] = {}
    for ann in annotations:
        if "AnnotationType_ObjectIdChanged" in ann.type:
            orig_ids = ann.details.get("orig_id", [])
            new_ids = ann.details.get("new_id", [])
            if orig_ids and new_ids:
                changes[orig_ids[0]] = new_ids[0]
    return changes


def infer_actions(
    prev: GameSnapshot,
    curr: GameSnapshot,
    card_names: dict[int, str],
) -> list[ReplayAction]:
    """Infer game actions from the diff between two snapshots."""
    actions: list[ReplayAction] = []
    turn = curr.turn_info.turn_number
    active = curr.turn_info.active_player

    # Build zone type lookup for current state
    zone_types: dict[int, str] = {}
    zone_owners: dict[int, int] = {}
    for z in curr.zones.values():
        zone_types[z.zone_id] = z.type
        zone_owners[z.zone_id] = z.owner_seat_id

    # Get ObjectIdChanged mappings
    id_changes = extract_object_id_changes(curr.annotations)

    for orig_id, new_id in id_changes.items():
        # Find the old object in prev state, new object in curr state
        old_obj = prev.game_objects.get(orig_id)
        new_obj = curr.game_objects.get(new_id)

        if old_obj is None or new_obj is None:
            continue

        old_zone_type = zone_types.get(old_obj.zone_id, prev.zones.get(old_obj.zone_id, Zone(0, "")).type)
        new_zone_type = zone_types.get(new_obj.zone_id, "")
        card_name = card_names.get(new_obj.grp_id, f"Unknown({new_obj.grp_id})")

        # Land play: hand -> battlefield, card is a land
        if (
            old_zone_type == "ZoneType_Hand"
            and new_zone_type == "ZoneType_Battlefield"
            and "CardType_Land" in new_obj.card_types
        ):
            actions.append(ReplayAction(
                action_type="land_play",
                turn_number=turn,
                active_player=active,
                player_seat_id=new_obj.controller_seat_id,
                card_name=card_name,
                grp_id=new_obj.grp_id,
                instance_id=new_id,
                source_zone="ZoneType_Hand",
                dest_zone="ZoneType_Battlefield",
            ))

        # Spell cast: hand -> stack
        elif old_zone_type == "ZoneType_Hand" and new_zone_type == "ZoneType_Stack":
            actions.append(ReplayAction(
                action_type="spell_cast",
                turn_number=turn,
                active_player=active,
                player_seat_id=new_obj.controller_seat_id,
                card_name=card_name,
                grp_id=new_obj.grp_id,
                instance_id=new_id,
                source_zone="ZoneType_Hand",
                dest_zone="ZoneType_Stack",
            ))

        # Draw: library -> hand
        elif old_zone_type == "ZoneType_Library" and new_zone_type == "ZoneType_Hand":
            actions.append(ReplayAction(
                action_type="draw",
                turn_number=turn,
                active_player=active,
                player_seat_id=new_obj.owner_seat_id,
                card_name=card_name,
                grp_id=new_obj.grp_id,
                instance_id=new_id,
                source_zone="ZoneType_Library",
                dest_zone="ZoneType_Hand",
            ))

        # Creature death: -> graveyard (from battlefield)
        elif (
            old_zone_type == "ZoneType_Battlefield"
            and new_zone_type == "ZoneType_Graveyard"
            and "CardType_Creature" in getattr(old_obj, "card_types", [])
        ):
            actions.append(ReplayAction(
                action_type="creature_death",
                turn_number=turn,
                active_player=active,
                player_seat_id=new_obj.owner_seat_id,
                card_name=card_name,
                grp_id=new_obj.grp_id,
                instance_id=new_id,
                source_zone="ZoneType_Battlefield",
                dest_zone="ZoneType_Graveyard",
            ))

        # Generic zone transition for anything else
        elif old_zone_type != new_zone_type:
            actions.append(ReplayAction(
                action_type="zone_transition",
                turn_number=turn,
                active_player=active,
                player_seat_id=new_obj.owner_seat_id,
                card_name=card_name,
                grp_id=new_obj.grp_id,
                instance_id=new_id,
                source_zone=old_zone_type,
                dest_zone=new_zone_type,
            ))

    # Ability activations: new GameObjectType_Ability on stack
    for iid, obj in curr.game_objects.items():
        if obj.type == "GameObjectType_Ability" and iid not in prev.game_objects:
            zone_type = zone_types.get(obj.zone_id, "")
            if zone_type == "ZoneType_Stack":
                source_name = card_names.get(obj.object_source_grp_id or 0, "")
                actions.append(ReplayAction(
                    action_type="ability_activation",
                    turn_number=turn,
                    active_player=active,
                    player_seat_id=obj.controller_seat_id,
                    card_name=source_name,
                    grp_id=obj.object_source_grp_id or 0,
                    instance_id=iid,
                    source_zone="",
                    dest_zone="ZoneType_Stack",
                    details={"parent_id": obj.parent_id},
                ))

    # Ability resolutions: GameObjectType_Ability was on stack in prev but is gone in curr
    prev_zone_types: dict[int, str] = {z.zone_id: z.type for z in prev.zones.values()}
    for iid, obj in prev.game_objects.items():
        if (
            obj.type == "GameObjectType_Ability"
            and iid not in curr.game_objects
            and prev_zone_types.get(obj.zone_id, "") == "ZoneType_Stack"
        ):
            source_name = card_names.get(obj.object_source_grp_id or 0, "")
            actions.append(ReplayAction(
                action_type="ability_resolution",
                turn_number=turn,
                active_player=active,
                player_seat_id=obj.controller_seat_id,
                card_name=source_name,
                grp_id=obj.object_source_grp_id or 0,
                instance_id=iid,
                source_zone="ZoneType_Stack",
                dest_zone="",
                details={"parent_id": obj.parent_id},
            ))

    # Auto-resolved abilities (created & deleted in same diff): detect via annotations
    # AnnotationType_ResolveTrigger / AnnotationType_TriggerAbility point to ability objects
    # that never persisted long enough to appear in prev or curr game_objects.
    _detected_ability_iids: set[int] = {
        a.instance_id
        for a in actions
        if a.action_type in ("ability_activation", "ability_resolution")
    }
    for ann in curr.annotations:
        if not (
            "AnnotationType_ResolveTrigger" in ann.type
            or "AnnotationType_TriggerAbility" in ann.type
        ):
            continue
        affector_id = ann.affector_id
        if affector_id in _detected_ability_iids:
            continue
        # Look up the ability object from prev (most likely) or curr
        ability_obj = prev.game_objects.get(affector_id) or curr.game_objects.get(affector_id)
        if ability_obj is None or ability_obj.type != "GameObjectType_Ability":
            continue
        source_name = card_names.get(ability_obj.object_source_grp_id or 0, "")
        if not source_name:
            continue
        actions.append(ReplayAction(
            action_type="ability_resolution",
            turn_number=turn,
            active_player=active,
            player_seat_id=ability_obj.controller_seat_id,
            card_name=source_name,
            grp_id=ability_obj.object_source_grp_id or 0,
            instance_id=affector_id,
            source_zone="",
            dest_zone="",
            details={"parent_id": ability_obj.parent_id},
        ))
        _detected_ability_iids.add(affector_id)

    # Combat phase detection
    prev_step = prev.turn_info.step
    curr_step = curr.turn_info.step
    combat_steps = {"Step_BeginCombat", "Step_DeclareAttack", "Step_DeclareBlock", "Step_CombatDamage", "Step_EndCombat"}
    if curr_step in combat_steps and prev_step != curr_step:
        actions.append(ReplayAction(
            action_type="combat",
            turn_number=turn,
            active_player=active,
            details={"step": curr_step, "prev_step": prev_step},
        ))

    return actions


class ObjectTracker:
    """Track card identity across zone transitions via ObjectIdChanged."""

    def __init__(self) -> None:
        # Maps current instanceId -> original instanceId
        self._id_chain: dict[int, int] = {}
        # Maps current instanceId -> grpId
        self._grp_ids: dict[int, int] = {}

    def register(self, instance_id: int, grp_id: int) -> None:
        """Register an initial object."""
        self._id_chain[instance_id] = instance_id
        self._grp_ids[instance_id] = grp_id

    def apply_id_change(self, orig_id: int, new_id: int, grp_id: int | None = None) -> None:
        """Record an ObjectIdChanged transition."""
        # The new ID maps to the same original as the old one
        original = self._id_chain.get(orig_id, orig_id)
        self._id_chain[new_id] = original
        if grp_id is not None:
            self._grp_ids[new_id] = grp_id
        elif orig_id in self._grp_ids:
            self._grp_ids[new_id] = self._grp_ids[orig_id]

    def get_original_id(self, current_id: int) -> int:
        """Get the original instanceId for a current instanceId."""
        return self._id_chain.get(current_id, current_id)

    def get_grp_id(self, current_id: int) -> int:
        """Get the grpId for a current instanceId."""
        return self._grp_ids.get(current_id, 0)

    def get_all_ids_for_original(self, original_id: int) -> list[int]:
        """Get all instanceIds that trace back to an original."""
        return [cid for cid, oid in self._id_chain.items() if oid == original_id]
