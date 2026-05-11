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
# Ability resolution tests
# ---------------------------------------------------------------------------

# grpId for a test gain-land (arbitrary non-zero value not in card_id_map)
_GAIN_LAND_GRP = 99001
_GAIN_LAND_NAME = "TestGainLand"


class _GainLandCard:
    """Minimal card stub whose register_triggers gives the controller +1 life."""

    name = _GAIN_LAND_NAME
    card_types: set = set()

    def __init__(self, owner: Any = None, controller: Any = None) -> None:
        self.owner = owner
        self.controller = controller
        self._grp_id = _GAIN_LAND_GRP
        self.is_tapped = False

    def register_triggers(self, game: Any) -> None:
        if self.controller is not None:
            self.controller.life += 1


class _MinimalRegistry:
    """Registry stub that vends _GainLandCard for _GAIN_LAND_NAME."""

    def __contains__(self, name: str) -> bool:
        return name == _GAIN_LAND_NAME

    def create_instance(self, name: str, owner: Any = None) -> _GainLandCard:
        card = _GainLandCard(owner=owner, controller=owner)
        return card


def _ability_snapshots(
    *,
    seat_id: int = 1,
    p1_life_snap0: int = 20,
    p1_life_snap1: int = 20,
    p1_life_snap2: int = 21,
    ability_in_snap1: bool = True,
) -> tuple[GameSnapshot, GameSnapshot, GameSnapshot]:
    """Build three snapshots representing a two-step ETB ability lifecycle.

    snap0 → snap1: land on battlefield, ability appears on stack (or auto-resolves)
    snap1 → snap2: ability resolves (gone from stack), life updated
    """
    def _base(gsid: int, life1: int, life2: int) -> GameSnapshot:
        s = GameSnapshot(game_state_id=gsid)
        s.players = {
            1: PlayerInfo(seat_id=1, life_total=life1),
            2: PlayerInfo(seat_id=2, life_total=life2),
        }
        s.zones[10] = ReplayZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[])
        s.zones[11] = ReplayZone(zone_id=11, type="ZoneType_Library", owner_seat_id=1, object_instance_ids=[])
        s.zones[20] = ReplayZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[])
        s.zones[21] = ReplayZone(zone_id=21, type="ZoneType_Library", owner_seat_id=2, object_instance_ids=[])
        s.zones[30] = ReplayZone(zone_id=30, type="ZoneType_Battlefield", owner_seat_id=1, object_instance_ids=[])
        s.zones[40] = ReplayZone(zone_id=40, type="ZoneType_Stack", owner_seat_id=0, object_instance_ids=[])
        return s

    snap0 = _base(1, p1_life_snap0, 20)

    snap1 = _base(2, p1_life_snap1, 20)
    # Land on battlefield
    snap1.zones[30].object_instance_ids = [501]
    snap1.game_objects[501] = GameObject(
        instance_id=501, grp_id=_GAIN_LAND_GRP, type="GameObjectType_Card",
        zone_id=30, owner_seat_id=1, controller_seat_id=1,
        object_source_grp_id=_GAIN_LAND_GRP,
    )
    if ability_in_snap1:
        # ETB ability on stack
        snap1.zones[40].object_instance_ids = [601]
        snap1.game_objects[601] = GameObject(
            instance_id=601, grp_id=0, type="GameObjectType_Ability",
            zone_id=40, owner_seat_id=1, controller_seat_id=1,
            parent_id=501, object_source_grp_id=_GAIN_LAND_GRP,
        )

    snap2 = _base(3, p1_life_snap2, 20)
    # Land still on battlefield, ability resolved (gone from stack)
    snap2.zones[30].object_instance_ids = [501]
    snap2.game_objects[501] = snap1.game_objects[501]

    return snap0, snap1, snap2


class TestAbilityResolution:
    """Tests for ETB ability resolution via engine path and snapshot-diff fallback."""

    def _executor(
        self,
        *snaps: GameSnapshot,
        seat_id: int = 1,
        registry: Any = None,
        card_id_map: dict[int, str] | None = None,
    ) -> ReplayExecutor:
        cid_map = card_id_map or {_GAIN_LAND_GRP: _GAIN_LAND_NAME, MOUNTAIN: "Mountain", PLAINS: "Plains"}
        replay = ReplayGame(seat_id=seat_id, opponent_seat_id=2, snapshots=list(snaps))
        ex = ReplayExecutor(replay, card_id_map=cid_map, registry=registry)
        ex.initialize(snaps[0])
        return ex

    def _seed_land_on_bf(self, ex: ReplayExecutor, snap1: GameSnapshot) -> None:
        """Place the gain land into the executor's engine battlefield to mirror snap1."""
        from engine.types import Zone

        player = ex.players[1]
        card = ex._create_card(_GAIN_LAND_GRP, player)
        card._grp_id = _GAIN_LAND_GRP
        player.zones[Zone.BATTLEFIELD].add(card)
        ex._engine_cards[501] = card

    # ------------------------------------------------------------------

    def test_ability_resolution_engine_path_life_gain(self) -> None:
        """Engine path: registered card's register_triggers gives +1 life, no divergence."""
        snap0, snap1, snap2 = _ability_snapshots()
        ex = self._executor(snap0, snap1, snap2, registry=_MinimalRegistry())

        # Simulate snap0→snap1: land was played (engine state = land on BF, ability on stack)
        self._seed_land_on_bf(ex, snap1)

        # snap1→snap2: ability resolves, life should go to 21
        result = ex.execute_step(snap1, snap2)

        life_mismatches = [m for m in result.mismatches if m.category == "life_total"]
        assert life_mismatches == [], f"Unexpected life mismatches: {life_mismatches}"
        assert ex.players[1].life == 21

    def test_ability_resolution_fallback_life_gain(self) -> None:
        """Fallback path: no registry, snapshot-diff applied, life reaches 21."""
        snap0, snap1, snap2 = _ability_snapshots()
        ex = self._executor(snap0, snap1, snap2, registry=None)

        self._seed_land_on_bf(ex, snap1)

        result = ex.execute_step(snap1, snap2)

        life_mismatches = [m for m in result.mismatches if m.category == "life_total"]
        assert life_mismatches == [], f"Unexpected life mismatches: {life_mismatches}"
        assert ex.players[1].life == 21

    def test_fallback_logs_warning(self) -> None:
        """Fallback must emit a WARNING-level log so engine gaps are visible."""
        import logging

        snap0, snap1, snap2 = _ability_snapshots()
        ex = self._executor(snap0, snap1, snap2, registry=None)
        self._seed_land_on_bf(ex, snap1)

        log_records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                log_records.append(record)

        handler = _Capture()
        logging.getLogger("silverquillm.replay.executor").addHandler(handler)
        try:
            ex.execute_step(snap1, snap2)
        finally:
            logging.getLogger("silverquillm.replay.executor").removeHandler(handler)

        warning_messages = [r.getMessage() for r in log_records if r.levelno >= logging.WARNING]
        assert any("fallback" in m.lower() or "life delta" in m.lower() for m in warning_messages), (
            f"Expected a fallback warning, got: {warning_messages}"
        )

    def test_no_double_apply_across_activation_and_resolution(self) -> None:
        """ability_activation (still on stack) must be a no-op; life changes only at resolution."""
        snap0, snap1, snap2 = _ability_snapshots()
        ex = self._executor(snap0, snap1, snap2, registry=_MinimalRegistry())
        self._seed_land_on_bf(ex, snap1)

        # snap0→snap1: land enters, ability goes on stack (life still 20 in snapshot)
        result01 = ex.execute_step(snap0, snap1)
        assert ex.players[1].life == 20, "life should not change at activation time"
        life_mm = [m for m in result01.mismatches if m.category == "life_total"]
        assert life_mm == [], f"Unexpected life mismatch at activation: {life_mm}"

        # snap1→snap2: ability resolves (life should become 21)
        result12 = ex.execute_step(snap1, snap2)
        assert ex.players[1].life == 21, "life should be 21 after resolution"
        life_mm2 = [m for m in result12.mismatches if m.category == "life_total"]
        assert life_mm2 == [], f"Unexpected life mismatch at resolution: {life_mm2}"

    def test_opponent_ability_resolution_fallback(self) -> None:
        """Opponent ability (seat 2) resolves via fallback; life changes correctly."""
        snap0, snap1, snap2 = _ability_snapshots(seat_id=2, p1_life_snap2=20)

        # Build snap2 with OPPONENT gaining life instead
        snap0_adj, snap1_adj, snap2_adj = _ability_snapshots()
        # Override: p2 life goes from 20 to 21, p1 stays 20
        snap2_adj.players[2] = PlayerInfo(seat_id=2, life_total=21)

        replay = ReplayGame(seat_id=1, opponent_seat_id=2, snapshots=[snap0_adj, snap1_adj, snap2_adj])
        ex = ReplayExecutor(replay, card_id_map={_GAIN_LAND_GRP: _GAIN_LAND_NAME})
        ex.initialize(snap0_adj)

        # Place land on p1's BF (opponent for seat-2 replay), ability in stack
        from engine.types import Zone
        p2 = ex.players[2]
        card = ex._create_card(_GAIN_LAND_GRP, p2)
        card._grp_id = _GAIN_LAND_GRP
        p2.zones[Zone.BATTLEFIELD].add(card)
        ex._engine_cards[501] = card

        result = ex.execute_step(snap1_adj, snap2_adj)

        assert ex.players[2].life == 21
        life_mm = [m for m in result.mismatches if m.category == "life_total"]
        assert life_mm == [], f"Unexpected life mismatches: {life_mm}"


# ---------------------------------------------------------------------------
# Life reconciliation tests
# ---------------------------------------------------------------------------


def _life_snap(
    gsid: int,
    step: str = "Step_CombatDamage",
    p1_life: int = 20,
    p2_life: int = 20,
    grp_ids_p1: list[int] | None = None,
    grp_ids_p2: list[int] | None = None,
) -> GameSnapshot:
    """Minimal snapshot with configurable life totals and optional battlefield cards."""
    s = GameSnapshot(game_state_id=gsid)
    s.players = {
        1: PlayerInfo(seat_id=1, life_total=p1_life),
        2: PlayerInfo(seat_id=2, life_total=p2_life),
    }
    s.turn_info = TurnInfo(step=step, turn_number=1, active_player=1)
    s.zones[10] = ReplayZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[])
    s.zones[11] = ReplayZone(zone_id=11, type="ZoneType_Library", owner_seat_id=1, object_instance_ids=[])
    s.zones[12] = ReplayZone(zone_id=12, type="ZoneType_Battlefield", owner_seat_id=1, object_instance_ids=[])
    s.zones[20] = ReplayZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[])
    s.zones[21] = ReplayZone(zone_id=21, type="ZoneType_Library", owner_seat_id=2, object_instance_ids=[])
    s.zones[22] = ReplayZone(zone_id=22, type="ZoneType_Battlefield", owner_seat_id=2, object_instance_ids=[])
    s.zones[30] = ReplayZone(zone_id=30, type="ZoneType_Graveyard", owner_seat_id=1, object_instance_ids=[])
    s.zones[31] = ReplayZone(zone_id=31, type="ZoneType_Graveyard", owner_seat_id=2, object_instance_ids=[])
    # Add battlefield cards if requested
    for grp_id in (grp_ids_p1 or []):
        iid = 100 + grp_id
        s.game_objects[iid] = GameObject(
            instance_id=iid, grp_id=grp_id, zone_id=12, owner_seat_id=1,
            controller_seat_id=1, type="GameObjectType_Card",
        )
        s.zones[12].object_instance_ids.append(iid)
    for grp_id in (grp_ids_p2 or []):
        iid = 200 + grp_id
        s.game_objects[iid] = GameObject(
            instance_id=iid, grp_id=grp_id, zone_id=22, owner_seat_id=2,
            controller_seat_id=2, type="GameObjectType_Card",
        )
        s.zones[22].object_instance_ids.append(iid)
    return s


class TestLifeReconciliation:
    """Tests for _reconcile_life_totals: general life total sync after every step."""

    def _executor(self, *snaps: GameSnapshot) -> ReplayExecutor:
        replay = ReplayGame(seat_id=1, opponent_seat_id=2, snapshots=list(snaps))
        ex = ReplayExecutor(replay, card_id_map={MOUNTAIN: "Mountain", PLAINS: "Plains"})
        ex.initialize(snaps[0])
        return ex

    def test_combat_damage_reduces_defender_life(self) -> None:
        """Defender takes 3 combat damage; reconciliation corrects engine life."""
        prev = _life_snap(1, "Step_DeclareAttack", p1_life=20, p2_life=20)
        curr = _life_snap(2, "Step_CombatDamage", p1_life=20, p2_life=17)

        ex = self._executor(prev, curr)
        result = ex.execute_step(prev, curr)

        assert ex.players[2].life == 17
        life_mm = [m for m in result.mismatches if m.category == "life_total"]
        assert life_mm == [], f"Unexpected life mismatches: {life_mm}"

    def test_both_players_take_damage(self) -> None:
        """Both players take damage in one step; both are reconciled."""
        prev = _life_snap(1, "Step_DeclareBlock", p1_life=20, p2_life=20)
        curr = _life_snap(2, "Step_CombatDamage", p1_life=18, p2_life=17)

        ex = self._executor(prev, curr)
        result = ex.execute_step(prev, curr)

        assert ex.players[1].life == 18
        assert ex.players[2].life == 17
        life_mm = [m for m in result.mismatches if m.category == "life_total"]
        assert life_mm == [], f"Unexpected life mismatches: {life_mm}"

    def test_life_change_during_no_action_step(self) -> None:
        """Snapshot with no inferred action still reconciles life totals."""
        prev = _life_snap(1, "Step_Upkeep", p1_life=20, p2_life=20)
        # No zone changes, no game objects — no actions will be inferred.
        # But life total changes (e.g., upkeep damage from a persistent effect).
        curr = _life_snap(2, "Step_Upkeep", p1_life=17, p2_life=20)

        ex = self._executor(prev, curr)
        result = ex.execute_step(prev, curr)

        assert ex.players[1].life == 17
        assert ex.players[2].life == 20
        life_mm = [m for m in result.mismatches if m.category == "life_total"]
        assert life_mm == [], f"Unexpected life mismatches: {life_mm}"

    def test_life_change_bundled_with_creature_death(self) -> None:
        """Life total drops in same snapshot a creature dies — reconciliation catches it."""
        # p2 has a creature on battlefield in prev; it's gone in curr (graveyard).
        prev = _life_snap(1, "Step_CombatDamage", p1_life=20, p2_life=20, grp_ids_p2=[MOUNTAIN])
        curr = _life_snap(2, "Step_EndOfCombat", p1_life=15, p2_life=20)
        # Move the creature to graveyard in curr
        iid = 200 + MOUNTAIN
        curr.game_objects[iid] = GameObject(
            instance_id=iid, grp_id=MOUNTAIN, zone_id=31, owner_seat_id=2,
            controller_seat_id=2, type="GameObjectType_Card",
        )
        curr.zones[31].object_instance_ids.append(iid)

        ex = self._executor(prev, curr)
        result = ex.execute_step(prev, curr)

        assert ex.players[1].life == 15
        life_mm = [m for m in result.mismatches if m.category == "life_total"]
        assert life_mm == [], f"Unexpected life mismatches: {life_mm}"

    def test_no_reconciliation_when_engine_is_correct(self, caplog) -> None:
        """When engine life already matches snapshot, no reconciliation log is emitted."""
        import logging
        prev = _life_snap(1, "Step_Main1", p1_life=20, p2_life=20)
        curr = _life_snap(2, "Step_Main1", p1_life=20, p2_life=20)

        ex = self._executor(prev, curr)
        with caplog.at_level(logging.INFO, logger="silverquillm.replay.executor"):
            ex.execute_step(prev, curr)

        reconcile_logs = [r for r in caplog.records if "Life reconciliation" in r.message]
        assert reconcile_logs == [], f"Unexpected reconciliation logs: {reconcile_logs}"


# ---------------------------------------------------------------------------
# Zone sync tests
# ---------------------------------------------------------------------------

class TestZoneSync:
    """Tests for _sync_zones: cards appearing without ObjectIdChanged annotations."""

    def _replay(self, *snapshots: GameSnapshot, seat_id: int = 1) -> ReplayGame:
        return ReplayGame(seat_id=seat_id, opponent_seat_id=2, snapshots=list(snapshots))

    def _hand_snap(
        self,
        gsid: int,
        grp_ids: list[int],
        seat_id: int = 1,
    ) -> GameSnapshot:
        """Snapshot with exactly the given grpIds in seat_id's hand, everything else empty."""
        snap = GameSnapshot(game_state_id=gsid)
        snap.players = {
            1: PlayerInfo(seat_id=1, life_total=20),
            2: PlayerInfo(seat_id=2, life_total=20),
        }
        iids = list(range(100, 100 + len(grp_ids)))
        other = 2 if seat_id == 1 else 1
        snap.zones[10] = ReplayZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=seat_id, object_instance_ids=iids)
        snap.zones[11] = ReplayZone(zone_id=11, type="ZoneType_Library", owner_seat_id=seat_id, object_instance_ids=[])
        snap.zones[20] = ReplayZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=other, object_instance_ids=[])
        snap.zones[21] = ReplayZone(zone_id=21, type="ZoneType_Library", owner_seat_id=other, object_instance_ids=[])
        for iid, grp_id in zip(iids, grp_ids):
            snap.game_objects[iid] = GameObject(
                instance_id=iid, grp_id=grp_id, type="GameObjectType_Card",
                zone_id=10, owner_seat_id=seat_id,
            )
        return snap

    def test_opening_hand_sync(self, card_id_map: dict[int, str]) -> None:
        """Empty hand at gsId=1 → 7-card hand at gsId=2 with no annotations: no zone mismatches."""
        snap0 = self._hand_snap(1, [])
        snap1 = self._hand_snap(2, [MOUNTAIN] * 4 + [PLAINS] * 3)

        ex = ReplayExecutor(self._replay(snap0, snap1), card_id_map=card_id_map)
        ex.initialize(snap0)
        result = ex.execute_step(snap0, snap1)

        zone_mismatches = [m for m in result.mismatches if m.category == "zone_contents"]
        assert zone_mismatches == [], f"Unexpected zone mismatches: {zone_mismatches}"

        from engine.types import Zone
        assert len(ex.players[1].zones[Zone.HAND]) == 7

    def test_mulligan_sync(self, card_id_map: dict[int, str]) -> None:
        """Hand shrinks from 7 to 6 after a mulligan (no ObjectIdChanged): engine synced."""
        snap0 = self._hand_snap(1, [MOUNTAIN] * 4 + [PLAINS] * 3)
        snap1 = self._hand_snap(2, [MOUNTAIN] * 3 + [PLAINS] * 3)  # 6 cards

        ex = ReplayExecutor(self._replay(snap0, snap1), card_id_map=card_id_map)
        ex.initialize(snap0)
        result = ex.execute_step(snap0, snap1)

        zone_mismatches = [m for m in result.mismatches if m.category == "zone_contents"]
        assert zone_mismatches == [], f"Unexpected zone mismatches after mulligan: {zone_mismatches}"

        from engine.types import Zone
        hand = ex.players[1].zones[Zone.HAND]
        assert len(hand) == 6

    def test_untracked_battlefield_appearance(self, card_id_map: dict[int, str]) -> None:
        """Card appears on battlefield without ObjectIdChanged (e.g. token): gets synced."""
        from engine.types import Zone

        def _base_snap(gsid: int) -> GameSnapshot:
            s = GameSnapshot(game_state_id=gsid)
            s.players = {1: PlayerInfo(seat_id=1, life_total=20), 2: PlayerInfo(seat_id=2, life_total=20)}
            s.zones[10] = ReplayZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[])
            s.zones[11] = ReplayZone(zone_id=11, type="ZoneType_Library", owner_seat_id=1, object_instance_ids=[])
            s.zones[20] = ReplayZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[])
            s.zones[21] = ReplayZone(zone_id=21, type="ZoneType_Library", owner_seat_id=2, object_instance_ids=[])
            s.zones[30] = ReplayZone(zone_id=30, type="ZoneType_Battlefield", owner_seat_id=1, object_instance_ids=[])
            return s

        snap0 = _base_snap(1)  # empty battlefield

        snap1 = _base_snap(2)
        snap1.zones[30].object_instance_ids = [501]
        snap1.game_objects[501] = GameObject(
            instance_id=501, grp_id=MOUNTAIN, type="GameObjectType_Card",
            zone_id=30, owner_seat_id=1,
        )

        ex = ReplayExecutor(self._replay(snap0, snap1), card_id_map=card_id_map)
        ex.initialize(snap0)
        result = ex.execute_step(snap0, snap1)

        zone_mismatches = [m for m in result.mismatches if m.category == "zone_contents"]
        assert zone_mismatches == [], f"Unexpected zone mismatches: {zone_mismatches}"

        bf = ex.players[1].zones[Zone.BATTLEFIELD]
        assert len(bf) == 1
        assert bf.get_all()[0].name == "Mountain"


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
