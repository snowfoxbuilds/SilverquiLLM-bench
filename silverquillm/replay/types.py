"""Data types for 17lands replay parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlayerInfo:
    """Player information from replay data."""

    seat_id: int
    life_total: int = 20
    status: str = "PlayerStatus_InGame"
    max_hand_size: int = 7


@dataclass
class TurnInfo:
    """Turn/phase/step information."""

    phase: str = ""
    step: str = ""
    turn_number: int = 0
    active_player: int = 0


@dataclass
class GameObject:
    """A card or ability on the battlefield/stack/etc."""

    instance_id: int
    grp_id: int
    type: str  # GameObjectType_Card or GameObjectType_Ability
    zone_id: int
    owner_seat_id: int = 0
    controller_seat_id: int = 0
    card_types: list[str] = field(default_factory=list)
    super_types: list[str] = field(default_factory=list)
    subtypes: list[str] = field(default_factory=list)
    color: list[str] = field(default_factory=list)
    power: int | None = None
    toughness: int | None = None
    visibility: str = "Visibility_Private"
    is_tapped: bool = False
    name: int = 0
    overlay_grp_id: int = 0
    parent_id: int | None = None
    object_source_grp_id: int | None = None
    viewers: list[int] = field(default_factory=list)
    # Combat state (protobuf default-omission: absent = not in combat)
    attack_state: str = ""
    block_state: str = ""
    attack_target_id: int = 0  # attackInfo.targetId (defending player seat)
    blocking_attacker_ids: list[int] = field(default_factory=list)  # blockInfo.attackerIds

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GameObject:
        """Create a GameObject from a raw GRE dict."""
        power_val = d.get("power", {}).get("value") if isinstance(d.get("power"), dict) else None
        tough_val = d.get("toughness", {}).get("value") if isinstance(d.get("toughness"), dict) else None
        return cls(
            instance_id=d["instanceId"],
            grp_id=d.get("grpId", 0),
            type=d.get("type", "GameObjectType_Card"),
            zone_id=d.get("zoneId", 0),
            owner_seat_id=d.get("ownerSeatId", 0),
            controller_seat_id=d.get("controllerSeatId", 0),
            card_types=d.get("cardTypes", []),
            super_types=d.get("superTypes", []),
            subtypes=d.get("subtypes", []),
            color=d.get("color", []),
            power=power_val,
            toughness=tough_val,
            visibility=d.get("visibility", "Visibility_Private"),
            is_tapped=d.get("isTapped", False),
            name=d.get("name", 0),
            overlay_grp_id=d.get("overlayGrpId", 0),
            parent_id=d.get("parentId"),
            object_source_grp_id=d.get("objectSourceGrpId"),
            viewers=d.get("viewers", []),
            attack_state=d.get("attackState", ""),
            block_state=d.get("blockState", ""),
            attack_target_id=d.get("attackInfo", {}).get("targetId", 0),
            blocking_attacker_ids=list(d.get("blockInfo", {}).get("attackerIds", [])),
        )


@dataclass
class Zone:
    """A game zone (hand, library, battlefield, etc.)."""

    zone_id: int
    type: str
    owner_seat_id: int = 0
    object_instance_ids: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Zone:
        return cls(
            zone_id=d["zoneId"],
            type=d.get("type", ""),
            owner_seat_id=d.get("ownerSeatId", 0),
            object_instance_ids=list(d.get("objectInstanceIds", [])),
        )


@dataclass
class Annotation:
    """An annotation recording what happened between states."""

    id: int
    affector_id: int = 0
    affected_ids: list[int] = field(default_factory=list)
    type: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Annotation:
        details: dict[str, Any] = {}
        for detail in d.get("details", []):
            key = detail.get("key", "")
            if "valueInt32" in detail:
                details[key] = detail["valueInt32"]
            elif "valueString" in detail:
                details[key] = detail["valueString"]
        return cls(
            id=d["id"],
            affector_id=d.get("affectorId", 0),
            affected_ids=d.get("affectedIds", []),
            type=d.get("type", []),
            details=details,
        )


@dataclass
class ReplayAction:
    """An inferred game action (land play, spell cast, draw, etc.)."""

    action_type: str  # "land_play", "spell_cast", "draw", "ability_activation", "creature_death", "combat"
    turn_number: int = 0
    active_player: int = 0
    player_seat_id: int = 0
    card_name: str = ""
    grp_id: int = 0
    instance_id: int = 0
    source_zone: str = ""
    dest_zone: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class GameInfo:
    """Match-level metadata."""

    match_id: str = ""
    game_number: int = 1
    stage: str = "GameStage_Start"
    game_type: str = ""
    variant: str = ""
    match_state: str = ""
    match_win_condition: str = ""
    super_format: str = ""
    mulligan_type: str = ""
    min_deck_size: int = 40
    max_deck_size: int = 250


@dataclass
class GameSnapshot:
    """A snapshot of the full game state at a given gameStateId."""

    game_state_id: int
    turn_info: TurnInfo = field(default_factory=TurnInfo)
    players: dict[int, PlayerInfo] = field(default_factory=dict)
    zones: dict[int, Zone] = field(default_factory=dict)
    game_objects: dict[int, GameObject] = field(default_factory=dict)
    annotations: list[Annotation] = field(default_factory=list)
    persistent_annotations: dict[int, Annotation] = field(default_factory=dict)
    actions: list[ReplayAction] = field(default_factory=list)
    game_info: GameInfo = field(default_factory=GameInfo)

    def get_zone_objects(self, zone_type: str, owner_seat_id: int | None = None) -> list[GameObject]:
        """Get all game objects in zones of the given type, optionally filtered by owner."""
        result = []
        for zone in self.zones.values():
            if zone.type != zone_type:
                continue
            if owner_seat_id is not None and zone.owner_seat_id != owner_seat_id:
                continue
            for iid in zone.object_instance_ids:
                obj = self.game_objects.get(iid)
                if obj is not None:
                    result.append(obj)
        return result

    def get_player_life(self, seat_id: int) -> int:
        """Get a player's life total."""
        player = self.players.get(seat_id)
        return player.life_total if player else 0


@dataclass
class ReplayGame:
    """Complete parsed replay game data."""

    seat_id: int
    opponent_seat_id: int
    game_info: GameInfo = field(default_factory=GameInfo)
    players: dict[int, PlayerInfo] = field(default_factory=dict)
    snapshots: list[GameSnapshot] = field(default_factory=list)
    actions: list[ReplayAction] = field(default_factory=list)
    initial_library: dict[int, list[int]] = field(default_factory=dict)  # seat_id -> list of grpIds
    result: str = ""  # "win", "loss", "draw", or ""

    def get_snapshot(self, game_state_id: int) -> GameSnapshot | None:
        """Get a snapshot by game state ID."""
        for snap in self.snapshots:
            if snap.game_state_id == game_state_id:
                return snap
        return None

    def get_actions_by_type(self, action_type: str) -> list[ReplayAction]:
        """Get all actions of a given type."""
        return [a for a in self.actions if a.action_type == action_type]

    def get_actions_on_turn(self, turn_number: int) -> list[ReplayAction]:
        """Get all actions for a given turn number."""
        return [a for a in self.actions if a.turn_number == turn_number]
