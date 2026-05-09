"""Tests for 17lands GRE replay parser."""

import json
from pathlib import Path

import pytest

from silverquillm.replay import parse_replay, ReplayGame, GameSnapshot, ReplayAction
from silverquillm.replay.parser import load_card_id_map
from silverquillm.replay.state import (
    apply_full_state,
    apply_diff,
    extract_object_id_changes,
    infer_actions,
    ObjectTracker,
)
from silverquillm.replay.types import (
    Annotation,
    GameInfo,
    GameObject,
    PlayerInfo,
    TurnInfo,
    Zone,
)


SAMPLE_REPLAY_PATH = Path(__file__).parent.parent / "data" / "replays" / "sample_replay.json"
CARD_ID_MAP_PATH = Path(__file__).parent.parent / "data" / "replays" / "card_id_map.json"

# Known grpIds from the synthetic sample data
MOUNTAIN = 95197
PLAINS = 95191
FOREST = 95199
SWAMP = 95195
SAVANNAH_LIONS = 93859
LLANOWAR_ELVES = 93940


@pytest.fixture
def sample_replay_data():
    """Load sample replay JSON."""
    with open(SAMPLE_REPLAY_PATH) as f:
        return json.load(f)


@pytest.fixture
def card_id_map():
    """Load card ID map."""
    return load_card_id_map(CARD_ID_MAP_PATH)


@pytest.fixture
def parsed_game(sample_replay_data, card_id_map):
    """Parse the sample replay into a ReplayGame."""
    return parse_replay(sample_replay_data, card_id_map=card_id_map)


class TestCardIdMap:
    """Test card ID mapping loading."""

    def test_load_card_id_map(self, card_id_map):
        assert len(card_id_map) > 0
        assert card_id_map[MOUNTAIN] == "Mountain"
        assert card_id_map[PLAINS] == "Plains"
        assert card_id_map[FOREST] == "Forest"
        assert card_id_map[SWAMP] == "Swamp"

    def test_load_missing_path(self):
        result = load_card_id_map("/nonexistent/path.json")
        assert result == {}


class TestGameSetup:
    """Test correct game setup parsing."""

    def test_seat_ids(self, parsed_game):
        assert parsed_game.seat_id == 1
        assert parsed_game.opponent_seat_id == 2

    def test_game_info(self, parsed_game):
        gi = parsed_game.game_info
        assert gi.match_win_condition == "MatchWinCondition_Best2of3"
        assert gi.super_format == "SuperFormat_Limited"
        assert gi.mulligan_type == "MulliganType_London"
        assert gi.game_type == "GameType_Duel"

    def test_players(self, parsed_game):
        assert 1 in parsed_game.players
        assert 2 in parsed_game.players
        assert parsed_game.players[1].life_total == 20
        assert parsed_game.players[2].life_total == 20

    def test_initial_library(self, parsed_game):
        """Initial library should contain grpIds of cards in library at game start."""
        assert 1 in parsed_game.initial_library
        assert 2 in parsed_game.initial_library
        assert len(parsed_game.initial_library[1]) > 0
        assert len(parsed_game.initial_library[2]) > 0


class TestOpeningHands:
    """Test opening hand detection."""

    def test_seat1_opening_hand_size(self, parsed_game):
        first_snap = parsed_game.snapshots[0]
        hand_objects = first_snap.get_zone_objects("ZoneType_Hand", owner_seat_id=1)
        assert len(hand_objects) == 7

    def test_seat2_opening_hand_size(self, parsed_game):
        first_snap = parsed_game.snapshots[0]
        hand_objects = first_snap.get_zone_objects("ZoneType_Hand", owner_seat_id=2)
        assert len(hand_objects) == 7

    def test_seat1_hand_contents(self, parsed_game):
        first_snap = parsed_game.snapshots[0]
        hand_objects = first_snap.get_zone_objects("ZoneType_Hand", owner_seat_id=1)
        grp_ids = [obj.grp_id for obj in hand_objects]
        # Should contain Mountains, Plains, and Savannah Lions
        assert grp_ids.count(MOUNTAIN) == 4  # 3 + 1 extra
        assert grp_ids.count(PLAINS) == 2
        assert SAVANNAH_LIONS in grp_ids


class TestStateReconstruction:
    """Test GRE state reconstruction (full + diffs)."""

    def test_full_state_creates_snapshot(self, sample_replay_data):
        gsm = sample_replay_data["events"][0]["gameStateMessage"]
        snap = apply_full_state(gsm)
        assert snap.game_state_id == 1
        assert len(snap.players) == 2
        assert len(snap.zones) > 0
        assert len(snap.game_objects) > 0

    def test_diff_merges_turn_info(self, sample_replay_data):
        gsm1 = sample_replay_data["events"][0]["gameStateMessage"]
        gsm2 = sample_replay_data["events"][1]["gameStateMessage"]
        snap1 = apply_full_state(gsm1)
        snap2 = apply_diff(snap1, gsm2)
        assert snap2.turn_info.turn_number == 1
        assert snap2.turn_info.active_player == 2

    def test_diff_merges_zones(self, sample_replay_data):
        """Zone diffs replace entire zone contents."""
        gsm1 = sample_replay_data["events"][0]["gameStateMessage"]
        snap1 = apply_full_state(gsm1)
        # After opponent plays Forest, hand zone 32 should have 6 cards
        gsm3 = sample_replay_data["events"][2]["gameStateMessage"]
        snap2 = apply_diff(snap1, sample_replay_data["events"][1]["gameStateMessage"])
        snap3 = apply_diff(snap2, gsm3)
        hand_zone = snap3.zones[32]
        assert len(hand_zone.object_instance_ids) == 6
        # Battlefield should now have 1 object
        bf_zone = snap3.zones[28]
        assert len(bf_zone.object_instance_ids) == 1

    def test_diff_upserts_game_objects(self, sample_replay_data):
        gsm1 = sample_replay_data["events"][0]["gameStateMessage"]
        snap1 = apply_full_state(gsm1)
        snap2 = apply_diff(snap1, sample_replay_data["events"][1]["gameStateMessage"])
        gsm3 = sample_replay_data["events"][2]["gameStateMessage"]
        snap3 = apply_diff(snap2, gsm3)
        # New object 301 (Forest on battlefield) should exist
        assert 301 in snap3.game_objects
        assert snap3.game_objects[301].grp_id == FOREST

    def test_diff_deletes_instance_ids(self, sample_replay_data):
        gsm1 = sample_replay_data["events"][0]["gameStateMessage"]
        snap1 = apply_full_state(gsm1)
        assert 201 in snap1.game_objects
        snap2 = apply_diff(snap1, sample_replay_data["events"][1]["gameStateMessage"])
        gsm3 = sample_replay_data["events"][2]["gameStateMessage"]
        snap3 = apply_diff(snap2, gsm3)
        # Object 201 should be deleted (moved to 301)
        assert 201 not in snap3.game_objects

    def test_snapshot_count(self, parsed_game):
        """Should have one snapshot per event with a gameStateMessage."""
        assert len(parsed_game.snapshots) > 0
        # Each event with a valid GSM produces a snapshot
        ids = [s.game_state_id for s in parsed_game.snapshots]
        assert ids == sorted(ids)  # Should be in order


class TestLandPlays:
    """Test land play detection across turns."""

    def test_turn1_opponent_plays_forest(self, parsed_game):
        t1_actions = parsed_game.get_actions_on_turn(1)
        land_plays = [a for a in t1_actions if a.action_type == "land_play"]
        assert len(land_plays) == 1
        assert land_plays[0].card_name == "Forest"
        assert land_plays[0].player_seat_id == 2

    def test_turn2_user_plays_mountain(self, parsed_game):
        t2_actions = parsed_game.get_actions_on_turn(2)
        land_plays = [a for a in t2_actions if a.action_type == "land_play"]
        assert len(land_plays) == 1
        assert land_plays[0].card_name == "Mountain"
        assert land_plays[0].player_seat_id == 1

    def test_turn3_opponent_plays_swamp(self, parsed_game):
        t3_actions = parsed_game.get_actions_on_turn(3)
        land_plays = [a for a in t3_actions if a.action_type == "land_play"]
        assert len(land_plays) == 1
        assert land_plays[0].card_name == "Swamp"
        assert land_plays[0].player_seat_id == 2

    def test_turn4_user_plays_plains(self, parsed_game):
        t4_actions = parsed_game.get_actions_on_turn(4)
        land_plays = [a for a in t4_actions if a.action_type == "land_play"]
        assert len(land_plays) == 1
        assert land_plays[0].card_name == "Plains"
        assert land_plays[0].player_seat_id == 1

    def test_turn5_opponent_plays_forest(self, parsed_game):
        t5_actions = parsed_game.get_actions_on_turn(5)
        land_plays = [a for a in t5_actions if a.action_type == "land_play"]
        assert len(land_plays) == 1
        assert land_plays[0].card_name == "Forest"
        assert land_plays[0].player_seat_id == 2

    def test_all_land_plays(self, parsed_game):
        all_lands = parsed_game.get_actions_by_type("land_play")
        assert len(all_lands) == 5
        names = [a.card_name for a in all_lands]
        assert names == ["Forest", "Mountain", "Swamp", "Plains", "Forest"]


class TestLifeTotals:
    """Test life total tracking."""

    def test_initial_life_totals(self, parsed_game):
        first_snap = parsed_game.snapshots[0]
        assert first_snap.get_player_life(1) == 20
        assert first_snap.get_player_life(2) == 20

    def test_life_totals_through_turn5(self, parsed_game):
        """Life totals should remain 20/20 through turn 5 (no combat/damage)."""
        last_snap = parsed_game.snapshots[-1]
        assert last_snap.get_player_life(1) == 20
        assert last_snap.get_player_life(2) == 20


class TestDraws:
    """Test draw action detection."""

    def test_turn2_draw(self, parsed_game):
        t2_actions = parsed_game.get_actions_on_turn(2)
        draws = [a for a in t2_actions if a.action_type == "draw"]
        assert len(draws) == 1
        assert draws[0].card_name == "Mountain"
        assert draws[0].player_seat_id == 1

    def test_turn4_draw(self, parsed_game):
        t4_actions = parsed_game.get_actions_on_turn(4)
        draws = [a for a in t4_actions if a.action_type == "draw"]
        assert len(draws) == 1
        assert draws[0].card_name == "Plains"
        assert draws[0].player_seat_id == 1


class TestObjectIdChanged:
    """Test ObjectIdChanged annotation tracking."""

    def test_extract_id_changes(self):
        annotations = [
            Annotation(
                id=1, affector_id=301, affected_ids=[201],
                type=["AnnotationType_ObjectIdChanged"],
                details={"orig_id": [201], "new_id": [301]},
            )
        ]
        changes = extract_object_id_changes(annotations)
        assert changes == {201: 301}

    def test_tracker_basic(self):
        tracker = ObjectTracker()
        tracker.register(101, MOUNTAIN)
        tracker.apply_id_change(101, 301, MOUNTAIN)
        assert tracker.get_original_id(301) == 101
        assert tracker.get_grp_id(301) == MOUNTAIN

    def test_tracker_chain(self):
        """Track across multiple zone transitions."""
        tracker = ObjectTracker()
        tracker.register(101, MOUNTAIN)
        tracker.apply_id_change(101, 301)  # hand -> battlefield
        tracker.apply_id_change(301, 501)  # battlefield -> graveyard
        assert tracker.get_original_id(501) == 101
        assert tracker.get_grp_id(501) == MOUNTAIN

    def test_land_play_tracked_via_object_id_change(self, parsed_game):
        """Land plays should be detected through ObjectIdChanged annotations."""
        # Turn 1: opponent's Forest 201 -> 301
        land_plays = parsed_game.get_actions_by_type("land_play")
        first_play = land_plays[0]
        assert first_play.source_zone == "ZoneType_Hand"
        assert first_play.dest_zone == "ZoneType_Battlefield"
        assert first_play.grp_id == FOREST


class TestReplayGameAPI:
    """Test ReplayGame convenience methods."""

    def test_get_snapshot(self, parsed_game):
        snap = parsed_game.get_snapshot(1)
        assert snap is not None
        assert snap.game_state_id == 1

    def test_get_snapshot_missing(self, parsed_game):
        snap = parsed_game.get_snapshot(999)
        assert snap is None

    def test_get_actions_by_type(self, parsed_game):
        draws = parsed_game.get_actions_by_type("draw")
        assert all(a.action_type == "draw" for a in draws)

    def test_get_actions_on_turn(self, parsed_game):
        t1 = parsed_game.get_actions_on_turn(1)
        assert all(a.turn_number == 1 for a in t1)


class TestGameObjectFromDict:
    """Test GameObject.from_dict parsing."""

    def test_basic_card(self):
        raw = {
            "instanceId": 123,
            "grpId": MOUNTAIN,
            "type": "GameObjectType_Card",
            "zoneId": 31,
            "ownerSeatId": 1,
            "controllerSeatId": 1,
            "cardTypes": ["CardType_Land"],
            "superTypes": ["SuperType_Basic"],
        }
        obj = GameObject.from_dict(raw)
        assert obj.instance_id == 123
        assert obj.grp_id == MOUNTAIN
        assert obj.card_types == ["CardType_Land"]

    def test_creature_with_power_toughness(self):
        raw = {
            "instanceId": 456,
            "grpId": SAVANNAH_LIONS,
            "type": "GameObjectType_Card",
            "zoneId": 31,
            "ownerSeatId": 1,
            "controllerSeatId": 1,
            "cardTypes": ["CardType_Creature"],
            "power": {"value": 2},
            "toughness": {"value": 1},
        }
        obj = GameObject.from_dict(raw)
        assert obj.power == 2
        assert obj.toughness == 1

    def test_ability_on_stack(self):
        raw = {
            "instanceId": 200,
            "grpId": 88024,
            "type": "GameObjectType_Ability",
            "zoneId": 27,
            "objectSourceGrpId": MOUNTAIN,
            "parentId": 199,
        }
        obj = GameObject.from_dict(raw)
        assert obj.type == "GameObjectType_Ability"
        assert obj.parent_id == 199
        assert obj.object_source_grp_id == MOUNTAIN


class TestParseFromPath:
    """Test parsing from file path."""

    def test_parse_from_path(self, card_id_map):
        game = parse_replay(SAMPLE_REPLAY_PATH, card_id_map=card_id_map)
        assert game.seat_id == 1
        assert len(game.snapshots) > 0


class TestAnnotationFromDict:
    """Test Annotation parsing."""

    def test_object_id_changed(self):
        raw = {
            "id": 1,
            "affectorId": 301,
            "affectedIds": [201],
            "type": ["AnnotationType_ObjectIdChanged"],
            "details": [
                {"key": "orig_id", "type": "KeyValuePairValueType_int32", "valueInt32": [201]},
                {"key": "new_id", "type": "KeyValuePairValueType_int32", "valueInt32": [301]},
            ],
        }
        ann = Annotation.from_dict(raw)
        assert ann.id == 1
        assert "AnnotationType_ObjectIdChanged" in ann.type
        assert ann.details["orig_id"] == [201]
        assert ann.details["new_id"] == [301]

    def test_string_detail(self):
        raw = {
            "id": 2,
            "type": ["AnnotationType_ShouldntPlay"],
            "details": [
                {"key": "Reason", "type": "KeyValuePairValueType_string", "valueString": ["EntersTapped"]},
            ],
        }
        ann = Annotation.from_dict(raw)
        assert ann.details["Reason"] == ["EntersTapped"]


class TestEdgeCases:
    """Test edge cases: empty events, missing fields, minimal input."""

    def test_empty_events_list(self, card_id_map):
        """Parsing replay with no events should produce empty game."""
        data = {"seat_id": 1, "opponent_seat_id": 2, "events": []}
        game = parse_replay(data, card_id_map=card_id_map)
        assert game.seat_id == 1
        assert game.snapshots == []
        assert game.actions == []

    def test_event_without_game_state_message(self, card_id_map):
        """Events missing gameStateMessage should be skipped gracefully."""
        data = {
            "seat_id": 1,
            "opponent_seat_id": 2,
            "events": [
                {"type": "GREMessageType_Something", "msgId": 1},
                {"type": "GREMessageType_Other"},
            ],
        }
        game = parse_replay(data, card_id_map=card_id_map)
        assert game.snapshots == []

    def test_diff_without_prior_full_is_skipped(self, card_id_map):
        """A diff event with no preceding full state should be skipped."""
        data = {
            "seat_id": 1,
            "opponent_seat_id": 2,
            "events": [
                {
                    "gameStateMessage": {
                        "type": "GameStateType_Diff",
                        "gameStateId": 2,
                        "turnInfo": {"turnNumber": 1},
                    }
                },
            ],
        }
        game = parse_replay(data, card_id_map=card_id_map)
        assert game.snapshots == []

    def test_full_state_minimal_fields(self):
        """Full state with only required gameStateId should not crash."""
        gsm = {"type": "GameStateType_Full", "gameStateId": 1}
        snap = apply_full_state(gsm)
        assert snap.game_state_id == 1
        assert len(snap.players) == 0
        assert len(snap.zones) == 0
        assert len(snap.game_objects) == 0

    def test_diff_preserves_zone_type_when_omitted(self):
        """If diff zone omits type, it should be preserved from previous snapshot."""
        full_gsm = {
            "type": "GameStateType_Full",
            "gameStateId": 1,
            "zones": [
                {"zoneId": 10, "type": "ZoneType_Hand", "ownerSeatId": 1, "objectInstanceIds": [1, 2]},
            ],
        }
        snap1 = apply_full_state(full_gsm)
        diff_gsm = {
            "type": "GameStateType_Diff",
            "gameStateId": 2,
            "zones": [
                {"zoneId": 10, "objectInstanceIds": [1]},  # type omitted
            ],
        }
        snap2 = apply_diff(snap1, diff_gsm)
        assert snap2.zones[10].type == "ZoneType_Hand"
        assert snap2.zones[10].object_instance_ids == [1]

    def test_diff_deletes_persistent_annotations(self):
        """diffDeletedPersistentAnnotationIds should remove persistent annotations."""
        full_gsm = {
            "type": "GameStateType_Full",
            "gameStateId": 1,
            "persistentAnnotations": [
                {"id": 10, "type": ["AnnotationType_SomePersistent"]},
                {"id": 11, "type": ["AnnotationType_Other"]},
            ],
        }
        snap1 = apply_full_state(full_gsm)
        assert 10 in snap1.persistent_annotations
        diff_gsm = {
            "type": "GameStateType_Diff",
            "gameStateId": 2,
            "diffDeletedPersistentAnnotationIds": [10],
        }
        snap2 = apply_diff(snap1, diff_gsm)
        assert 10 not in snap2.persistent_annotations
        assert 11 in snap2.persistent_annotations

    def test_get_player_life_missing_seat(self):
        """get_player_life should return 0 for nonexistent seat."""
        snap = GameSnapshot(game_state_id=1)
        assert snap.get_player_life(99) == 0

    def test_tracker_get_all_ids_for_original(self):
        """ObjectTracker.get_all_ids_for_original should return all IDs in chain."""
        tracker = ObjectTracker()
        tracker.register(100, MOUNTAIN)
        tracker.apply_id_change(100, 200)
        tracker.apply_id_change(200, 300)
        all_ids = tracker.get_all_ids_for_original(100)
        assert set(all_ids) == {100, 200, 300}

    def test_tracker_grp_id_inherited_without_explicit(self):
        """apply_id_change without grp_id should inherit from old ID."""
        tracker = ObjectTracker()
        tracker.register(50, PLAINS)
        tracker.apply_id_change(50, 60)
        assert tracker.get_grp_id(60) == PLAINS

    def test_tracker_unknown_id_returns_self(self):
        """get_original_id on unregistered ID should return the ID itself."""
        tracker = ObjectTracker()
        assert tracker.get_original_id(999) == 999
        assert tracker.get_grp_id(999) == 0


class TestGameSnapshotZoneQuery:
    """Test GameSnapshot.get_zone_objects filtering."""

    def test_get_zone_objects_no_owner_filter(self, parsed_game):
        """get_zone_objects without owner returns objects from all matching zones."""
        first_snap = parsed_game.snapshots[0]
        all_hand = first_snap.get_zone_objects("ZoneType_Hand")
        assert len(all_hand) == 14  # 7 + 7

    def test_get_zone_objects_nonexistent_zone_type(self, parsed_game):
        """Querying for a zone type that doesn't exist returns empty list."""
        first_snap = parsed_game.snapshots[0]
        result = first_snap.get_zone_objects("ZoneType_DoesNotExist")
        assert result == []
