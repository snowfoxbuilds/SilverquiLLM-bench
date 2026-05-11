"""Tests for the ReplayExecutor — state-diff observer mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.replay.executor import (
    ReplayExecutor,
    StateMismatch,
    StepResult,
    load_card_id_map,
)
from silverquillm.replay.parser import parse_replay
from silverquillm.replay.types import (
    GameSnapshot,
    GameObject,
    PlayerInfo,
    ReplayAction,
    ReplayGame,
    TurnInfo,
    Zone as ReplayZone,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_REPLAY_PATH = Path(__file__).parent.parent / "data" / "replays" / "sample_replay.json"
CARD_ID_MAP_PATH = Path(__file__).parent.parent / "data" / "replays" / "card_id_map.json"

# Known grpIds from sample data
MOUNTAIN = 95197
PLAINS = 95191


@pytest.fixture
def card_id_map() -> dict[int, str]:
    """Load the card ID map."""
    return load_card_id_map(CARD_ID_MAP_PATH)


@pytest.fixture
def sample_replay(card_id_map: dict[int, str]) -> ReplayGame:
    """Parse the sample replay."""
    return parse_replay(SAMPLE_REPLAY_PATH, card_id_map=card_id_map)


@pytest.fixture
def executor(sample_replay: ReplayGame, card_id_map: dict[int, str]) -> ReplayExecutor:
    """Create an initialized executor."""
    ex = ReplayExecutor(sample_replay, card_id_map=card_id_map)
    ex.initialize()
    return ex


def _make_minimal_snapshot(
    game_state_id: int = 1,
    p1_life: int = 20,
    p2_life: int = 20,
) -> GameSnapshot:
    """Build a minimal GameSnapshot with two players, hands, and libraries."""
    snap = GameSnapshot(game_state_id=game_state_id)
    snap.players = {
        1: PlayerInfo(seat_id=1, life_total=p1_life),
        2: PlayerInfo(seat_id=2, life_total=p2_life),
    }
    # Hand zones
    snap.zones[10] = ReplayZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[101, 102])
    snap.zones[20] = ReplayZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[201, 202])
    # Library zones
    snap.zones[11] = ReplayZone(zone_id=11, type="ZoneType_Library", owner_seat_id=1, object_instance_ids=[103])
    snap.zones[21] = ReplayZone(zone_id=21, type="ZoneType_Library", owner_seat_id=2, object_instance_ids=[203])
    # GameObjects — use Mountain grpId so cards resolve
    for iid in [101, 102, 103]:
        snap.game_objects[iid] = GameObject(
            instance_id=iid, grp_id=MOUNTAIN, type="GameObjectType_Card",
            zone_id=10 if iid <= 102 else 11, owner_seat_id=1,
        )
    for iid in [201, 202, 203]:
        snap.game_objects[iid] = GameObject(
            instance_id=iid, grp_id=PLAINS, type="GameObjectType_Card",
            zone_id=20 if iid <= 202 else 21, owner_seat_id=2,
        )
    return snap


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------

class TestReplayExecutorInit:
    """Tests for ReplayExecutor initialization."""

    def test_init_creates_players(self, executor: ReplayExecutor) -> None:
        assert 1 in executor.players
        assert 2 in executor.players

    def test_init_sets_life_totals(self, executor: ReplayExecutor) -> None:
        assert executor.players[1].life == 20
        assert executor.players[2].life == 20

    def test_init_creates_game_state(self, executor: ReplayExecutor) -> None:
        assert executor.game is not None

    def test_init_populates_hands(self, executor: ReplayExecutor) -> None:
        from engine.types import Zone
        p1_hand = executor.players[1].zones[Zone.HAND]
        p2_hand = executor.players[2].zones[Zone.HAND]
        assert len(p1_hand) == 7
        assert len(p2_hand) == 7

    def test_init_populates_libraries(self, executor: ReplayExecutor) -> None:
        from engine.types import Zone
        p1_lib = executor.players[1].zones[Zone.LIBRARY]
        p2_lib = executor.players[2].zones[Zone.LIBRARY]
        assert len(p1_lib) > 0
        assert len(p2_lib) > 0

    def test_init_hand_card_names(self, executor: ReplayExecutor) -> None:
        """Hand cards should have correct names from grpId mapping."""
        from engine.types import Zone
        hand = executor.players[1].zones[Zone.HAND]
        card_names = [c.name for c in hand.get_all()]
        # From sample replay: seat 1 hand has Mountains, Plains, Savannah Lions
        assert "Mountain" in card_names
        assert "Savannah Lions" in card_names or "Plains" in card_names

    def test_init_no_snapshots_raises(self) -> None:
        replay = ReplayGame(seat_id=1, opponent_seat_id=2)
        ex = ReplayExecutor(replay)
        with pytest.raises(ValueError, match="No snapshots"):
            ex.initialize()

    def test_init_from_explicit_snapshot(self, card_id_map: dict[int, str]) -> None:
        """initialize() should accept an explicit snapshot argument."""
        snap = _make_minimal_snapshot()
        replay = ReplayGame(seat_id=1, opponent_seat_id=2, snapshots=[snap])
        ex = ReplayExecutor(replay, card_id_map=card_id_map)
        ex.initialize(snap)
        assert ex._initialized
        assert 1 in ex.players
        assert 2 in ex.players


# ---------------------------------------------------------------------------
# Step execution tests
# ---------------------------------------------------------------------------

class TestReplayExecutorStep:
    """Tests for individual step execution."""

    def test_step_returns_step_result(
        self,
        executor: ReplayExecutor,
        sample_replay: ReplayGame,
    ) -> None:
        prev = sample_replay.snapshots[0]
        curr = sample_replay.snapshots[1]
        result = executor.execute_step(prev, curr)
        assert isinstance(result, StepResult)

    def test_step_result_has_snapshot_id(
        self,
        executor: ReplayExecutor,
        sample_replay: ReplayGame,
    ) -> None:
        prev = sample_replay.snapshots[0]
        curr = sample_replay.snapshots[1]
        result = executor.execute_step(prev, curr)
        assert result.snapshot_id == curr.game_state_id

    def test_uninitialized_step_raises(
        self,
        sample_replay: ReplayGame,
        card_id_map: dict[int, str],
    ) -> None:
        ex = ReplayExecutor(sample_replay, card_id_map=card_id_map)
        prev = sample_replay.snapshots[0]
        curr = sample_replay.snapshots[1]
        with pytest.raises(RuntimeError, match="initialize"):
            ex.execute_step(prev, curr)


# ---------------------------------------------------------------------------
# Full execution tests
# ---------------------------------------------------------------------------

class TestReplayExecutorExecuteAll:
    """Tests for execute_all over the full replay."""

    def test_execute_all_returns_results(
        self,
        executor: ReplayExecutor,
    ) -> None:
        results = executor.execute_all()
        # Should have one result per snapshot transition
        assert len(results) == len(executor.replay.snapshots) - 1

    def test_execute_all_results_are_step_results(
        self,
        executor: ReplayExecutor,
    ) -> None:
        results = executor.execute_all()
        for r in results:
            assert isinstance(r, StepResult)

    def test_execute_all_populates_results_list(
        self,
        executor: ReplayExecutor,
    ) -> None:
        executor.execute_all()
        assert executor.step_count > 0

    def test_execute_all_auto_initializes(
        self,
        sample_replay: ReplayGame,
        card_id_map: dict[int, str],
    ) -> None:
        """execute_all should auto-initialize if not already initialized."""
        ex = ReplayExecutor(sample_replay, card_id_map=card_id_map)
        results = ex.execute_all()
        assert ex._initialized
        assert len(results) > 0


# ---------------------------------------------------------------------------
# State comparison tests
# ---------------------------------------------------------------------------

class TestStateComparison:
    """Tests for state comparison between engine and snapshots."""

    def test_compare_life_totals_match(self, executor: ReplayExecutor) -> None:
        """After init (no actions), life totals should match snapshot 0."""
        snap = executor.replay.snapshots[0]
        mismatches = executor._compare_life_totals(snap)
        assert len(mismatches) == 0

    def test_compare_state_returns_list(self, executor: ReplayExecutor) -> None:
        snap = executor.replay.snapshots[0]
        result = executor.compare_state(snap)
        assert isinstance(result, list)

    def test_mismatch_str_representation(self) -> None:
        m = StateMismatch(
            category="life_total",
            description="Player 1 life mismatch",
            engine_value=20,
            snapshot_value=18,
        )
        s = str(m)
        assert "life_total" in s
        assert "20" in s
        assert "18" in s

    def test_step_result_matched_true_when_no_mismatches(self) -> None:
        """StepResult.matched should be True when mismatches list is empty."""
        r = StepResult(snapshot_id=1, mismatches=[])
        assert r.matched is True

    def test_step_result_matched_false_when_mismatches(self) -> None:
        """StepResult.matched should be False when mismatches are present."""
        r = StepResult(
            snapshot_id=1,
            mismatches=[StateMismatch(category="life_total", description="mismatch")],
        )
        assert r.matched is False

    def test_divergence_detected_life_total(self, executor: ReplayExecutor) -> None:
        """When engine life differs from snapshot, a life_total mismatch is reported."""
        snap = executor.replay.snapshots[0]
        # Manually alter engine life to create divergence
        executor.players[1].life = 15
        mismatches = executor._compare_life_totals(snap)
        assert len(mismatches) >= 1
        assert any(m.category == "life_total" and m.seat_id == 1 for m in mismatches)
        assert any(m.engine_value == 15 and m.snapshot_value == 20 for m in mismatches)


# ---------------------------------------------------------------------------
# Seat 1 vs Seat 2 behavior tests
# ---------------------------------------------------------------------------

class TestSeatBehavior:
    """Tests for seat-specific execution behavior."""

    def test_seat1_land_play(
        self,
        executor: ReplayExecutor,
        sample_replay: ReplayGame,
    ) -> None:
        """Seat 1 land play should move card from hand to battlefield in engine."""
        from engine.types import Zone

        for i in range(1, len(sample_replay.snapshots)):
            prev = sample_replay.snapshots[i - 1]
            curr = sample_replay.snapshots[i]
            result = executor.execute_step(prev, curr)

            if result.action_type == "land_play" and result.seat_id == 1:
                bf = executor.players[1].zones[Zone.BATTLEFIELD]
                bf_names = [c.name for c in bf.get_all()]
                assert "Mountain" in bf_names or "Plains" in bf_names
                break

    def test_seat2_oracle_injection(
        self,
        executor: ReplayExecutor,
        sample_replay: ReplayGame,
    ) -> None:
        """Seat 2 actions should be injected without legality checks."""
        from engine.types import Zone

        for i in range(1, len(sample_replay.snapshots)):
            prev = sample_replay.snapshots[i - 1]
            curr = sample_replay.snapshots[i]
            result = executor.execute_step(prev, curr)

            if result.seat_id == 2 and result.action_type == "land_play":
                bf = executor.players[2].zones[Zone.BATTLEFIELD]
                assert len(bf) > 0
                break

    def test_seat1_actions_validated_through_engine(
        self,
        executor: ReplayExecutor,
        sample_replay: ReplayGame,
    ) -> None:
        """Seat 1 actions should modify engine state (not just inject)."""
        from engine.types import Zone

        found_seat1_action = False
        for i in range(1, len(sample_replay.snapshots)):
            prev = sample_replay.snapshots[i - 1]
            curr = sample_replay.snapshots[i]
            hand_before = len(executor.players[1].zones[Zone.HAND])
            result = executor.execute_step(prev, curr)
            if result.seat_id == 1 and result.action_type in ("land_play", "spell_cast") and not result.skipped:
                found_seat1_action = True
                # After playing a card from hand, hand should have shrunk
                hand_after = len(executor.players[1].zones[Zone.HAND])
                assert hand_after < hand_before, "Hand should shrink after seat 1 plays a card"
                break
        assert found_seat1_action, "No seat 1 land/spell action found in sample replay"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests for the executor."""

    def test_empty_replay_execute_all(self) -> None:
        """execute_all on a replay with no snapshots should return empty list."""
        replay = ReplayGame(seat_id=1, opponent_seat_id=2, snapshots=[])
        ex = ReplayExecutor(replay)
        results = ex.execute_all()
        assert results == []

    def test_missing_card_in_card_id_map(self) -> None:
        """Cards with unknown grpId should get fallback names like Unknown_NNN."""
        snap = _make_minimal_snapshot()
        # Use a grpId not in the map
        snap.game_objects[101].grp_id = 999999
        replay = ReplayGame(seat_id=1, opponent_seat_id=2, snapshots=[snap])
        ex = ReplayExecutor(replay, card_id_map={MOUNTAIN: "Mountain", PLAINS: "Plains"})
        ex.initialize(snap)
        from engine.types import Zone
        hand = ex.players[1].zones[Zone.HAND]
        names = [c.name for c in hand.get_all()]
        assert any("Unknown" in n or "999999" in n for n in names)

    def test_single_snapshot_execute_all(self, card_id_map: dict[int, str]) -> None:
        """A replay with only one snapshot has no transitions; execute_all returns []."""
        snap = _make_minimal_snapshot()
        replay = ReplayGame(seat_id=1, opponent_seat_id=2, snapshots=[snap])
        ex = ReplayExecutor(replay, card_id_map=card_id_map)
        ex.initialize(snap)
        results = ex.execute_all()
        assert results == []


# ---------------------------------------------------------------------------
# Card ID map tests
# ---------------------------------------------------------------------------

class TestCardIdMap:
    """Tests for card ID map loading."""

    def test_load_card_id_map(self) -> None:
        mapping = load_card_id_map(CARD_ID_MAP_PATH)
        assert len(mapping) > 0
        assert MOUNTAIN in mapping
        assert mapping[MOUNTAIN] == "Mountain"

    def test_load_card_id_map_missing_file(self) -> None:
        mapping = load_card_id_map("/nonexistent/path.json")
        assert mapping == {}


# ---------------------------------------------------------------------------
# Import/export tests
# ---------------------------------------------------------------------------

class TestImports:
    """Test that all public API is importable from the package."""

    def test_import_replay_executor(self) -> None:
        from silverquillm.replay import ReplayExecutor
        assert ReplayExecutor is not None

    def test_import_state_mismatch(self) -> None:
        from silverquillm.replay import StateMismatch
        assert StateMismatch is not None

    def test_import_step_result(self) -> None:
        from silverquillm.replay import StepResult
        assert StepResult is not None
