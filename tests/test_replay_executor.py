"""Tests for the ReplayExecutor — state-diff observer mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from silverquillm.replay.executor import (
    ReplayExecutor,
    StateMismatch,
    StepResult,
    TokenIdMap,
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


# ---------------------------------------------------------------------------
# Counter annotation sync (Phase F) — CounterAdded/Removed -> engine counters
# ---------------------------------------------------------------------------

from silverquillm.replay.types import Annotation as _Annotation


class _FakePermanent:
    """Minimal stand-in for an engine permanent the reconcile writes onto."""

    def __init__(self, oid: int, name: str = "Test") -> None:
        self.object_id = oid
        self.name = name
        self.plus_one_counters = 0
        self._base_plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_minus_one_counters = 0
        self._generic_counters: dict[str, int] = {}


class _FakeToken:
    """Minimal engine token for the correlation -> counter-binding path.

    Carries the characteristic signature ``_engine_token_signature`` reads and
    the counter fields the reconcile writes, but NOT ``_grp_id`` (it starts
    id-less, exactly like a freshly minted engine token) and is deliberately
    absent from ``_engine_cards`` so the test exercises the token binding rather
    than a pre-seeded correlation.
    """

    def __init__(self, name: str = "Cat Token") -> None:
        self.name = name
        self.is_token = True
        self.card_types = ["creature"]
        self.subtypes = ["Cat"]
        self.base_power = 1
        self.base_toughness = 1
        self.plus_one_counters = 0
        self._base_plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_minus_one_counters = 0
        self._generic_counters: dict[str, int] = {}


def _counter_ann(ann_id: int, affected: list[int], ctype: int, amount: int,
                 removed: bool = False) -> _Annotation:
    kind = "AnnotationType_CounterRemoved" if removed else "AnnotationType_CounterAdded"
    return _Annotation(
        id=ann_id, affector_id=0, affected_ids=affected, type=[kind],
        details={"counter_type": [ctype], "transaction_amount": [amount]},
    )


def _ann_snap(
    game_state_id: int,
    *anns: _Annotation,
    bf: dict[int, int] | None = None,
    grp: dict[int, int] | None = None,
) -> GameSnapshot:
    """A minimal snapshot carrying counter annotations + GRE bf residency.

    ``bf`` maps affected instance ids to their controller seat: each becomes a
    GameObject in a shared GRE battlefield zone, because a fold now requires
    GRE itself to attest the affected object ON the battlefield in the current
    snapshot (stint-safe correlation). ``grp`` optionally assigns grpIds
    (default 0 — unknown, which contradicts nothing). Engine-side residency and
    stint identity are still set up directly via ``_place`` / ``_remove``.
    """
    snap = GameSnapshot(game_state_id=game_state_id)
    snap.players = {1: PlayerInfo(seat_id=1, life_total=20),
                    2: PlayerInfo(seat_id=2, life_total=20)}
    bf = bf or {}
    grp = grp or {}
    snap.zones[30] = ReplayZone(
        zone_id=30, type="ZoneType_Battlefield", owner_seat_id=0,
        object_instance_ids=list(bf),
    )
    for aid, seat in bf.items():
        snap.game_objects[aid] = GameObject(
            instance_id=aid, grp_id=grp.get(aid, 0),
            type="GameObjectType_Card", zone_id=30,
            owner_seat_id=seat, controller_seat_id=seat,
        )
    snap.annotations = list(anns)
    return snap


def _place(executor: ReplayExecutor, perm: object, aid: int, seat: int = 1) -> None:
    """Put an engine permanent on the engine battlefield and correlate its aid."""
    from engine.types import Zone

    executor.players[seat].zones[Zone.BATTLEFIELD].add(perm)
    executor._engine_cards[aid] = perm


def _remove(executor: ReplayExecutor, perm: object, seat: int = 1) -> None:
    """Blink: remove an engine permanent from the engine battlefield."""
    from engine.types import Zone

    executor.players[seat].zones[Zone.BATTLEFIELD].remove(perm)


class TestCounterAnnotationSync:
    """The GRE CounterAdded/Removed stream is reconciled onto the correlated
    engine permanent as an authoritative SET (double-count-proof). Identity is
    anchored to the engine object; retirement is an engine zone transition."""

    def test_plus_one_counter_synced_to_pt_fields(self, executor: ReplayExecutor) -> None:
        perm = _FakePermanent(999)
        _place(executor, perm, 5001)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(1, [5001], 1, 2), bf={5001: 1})
        )
        assert perm.plus_one_counters == 2
        assert perm._base_plus_one_counters == 2  # survives apply_all reset

    def test_named_counter_synced_to_generic(self, executor: ReplayExecutor) -> None:
        perm = _FakePermanent(1000, name="Drake Hatcher")
        _place(executor, perm, 5002)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(2, [5002], 200, 3), bf={5002: 1})
        )
        assert perm._generic_counters.get("incubation") == 3

    def test_authoritative_set_never_double_counts(self, executor: ReplayExecutor) -> None:
        # The engine already drove the counter to 2; GRE attests 2 -> the SET
        # is a no-op, not an addition (would be 4 under naive incremental add).
        perm = _FakePermanent(1001)
        perm.plus_one_counters = 2
        perm._base_plus_one_counters = 2
        _place(executor, perm, 5003)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(3, [5003], 1, 2), bf={5003: 1})
        )
        assert perm.plus_one_counters == 2

    def test_dedup_by_annotation_id(self, executor: ReplayExecutor) -> None:
        perm = _FakePermanent(1002)
        _place(executor, perm, 5004)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(4, [5004], 1, 1), bf={5004: 1})
        )
        # The same annotation id repeated in a later snapshot (persistent slot)
        # is not re-folded: exactly-once per (annotation, affected id).
        executor._apply_counter_annotations(
            _ann_snap(3, _counter_ann(4, [5004], 1, 1), bf={5004: 1})
        )
        assert perm.plus_one_counters == 1

    def test_counter_removed_decrements(self, executor: ReplayExecutor) -> None:
        perm = _FakePermanent(1003)
        _place(executor, perm, 5005)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(5, [5005], 1, 3), bf={5005: 1})
        )
        assert perm.plus_one_counters == 3
        executor._apply_counter_annotations(
            _ann_snap(3, _counter_ann(6, [5005], 1, 1, removed=True), bf={5005: 1})
        )
        assert perm.plus_one_counters == 2

    def test_ledger_never_goes_negative(self, executor: ReplayExecutor) -> None:
        perm = _FakePermanent(1004)
        _place(executor, perm, 5006)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(7, [5006], 1, 1, removed=True), bf={5006: 1})
        )
        assert perm.plus_one_counters == 0

    def test_unknown_affected_object_defers_not_raises(self, executor: ReplayExecutor) -> None:
        # An uncorrelated affected id is deferred (retryable), never applied nor
        # silently dropped — nothing to write onto, so nothing raises.
        executor._apply_counter_annotations(_ann_snap(2, _counter_ann(8, [99999], 1, 1)))
        assert (8, 99999) in executor._pending_counter_effects
        assert (8, 99999) not in executor._applied_counter_effects

    def test_object_without_ledger_untouched(self, executor: ReplayExecutor) -> None:
        # An engine object GRE never annotated is never zeroed by the reconcile.
        perm = _FakePermanent(1005)
        perm.plus_one_counters = 4  # engine-legit, no GRE annotation
        _place(executor, perm, 5007)
        other = _FakePermanent(1006)
        _place(executor, other, 5008)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(9, [5008], 1, 1), bf={5007: 1, 5008: 1})
        )
        assert perm.plus_one_counters == 4  # untouched
        assert other.plus_one_counters == 1


class TestCounterStintScoping:
    """A counter belongs to one battlefield stint (the GRE instance id). It
    never crosses a real zone-change boundary: the engine reuses the same Python
    object across a blink, but a returned permanent starts with no inherited
    counters unless a new annotation attests them."""

    def test_plus_one_not_restored_after_blink(self, executor: ReplayExecutor) -> None:
        # +1/+1, then leaves the engine battlefield and returns with NO new
        # annotation: the old counter is not restored on the reused object.
        perm = _FakePermanent(2000)
        _place(executor, perm, 6001)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(20, [6001], 1, 1), bf={6001: 1})
        )
        assert perm.plus_one_counters == 1

        # Blink out: perm leaves the engine battlefield -> retirement clears it.
        _remove(executor, perm)
        executor._apply_counter_annotations(_ann_snap(3))  # no annotation
        assert perm.plus_one_counters == 0
        assert perm._base_plus_one_counters == 0

        # Return with no new attestation: it stays clean (no inherited counter).
        _place(executor, perm, 6002)
        executor._apply_counter_annotations(_ann_snap(4, bf={6002: 1}))
        assert perm.plus_one_counters == 0

    def test_named_counter_not_restored_after_blink(self, executor: ReplayExecutor) -> None:
        # Same lifecycle for a named generic counter.
        perm = _FakePermanent(2001, name="Drake Hatcher")
        _place(executor, perm, 6101)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(21, [6101], 200, 4), bf={6101: 1})  # incubation x4
        )
        assert perm._generic_counters.get("incubation") == 4

        _remove(executor, perm)
        executor._apply_counter_annotations(_ann_snap(3))
        assert perm._generic_counters.get("incubation", 0) == 0

    def test_unrelated_counter_does_not_resurrect_old_ledger(
        self, executor: ReplayExecutor
    ) -> None:
        # After a blink, an unrelated permanent receiving a counter (which drives
        # global reconciliation) must not resurrect the retired object's ledger.
        perm = _FakePermanent(2002)
        _place(executor, perm, 6201)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(22, [6201], 1, 2), bf={6201: 1})
        )
        assert perm.plus_one_counters == 2

        # perm leaves the battlefield; an unrelated permanent enters and gets its
        # own counter.
        _remove(executor, perm)
        other = _FakePermanent(2003)
        _place(executor, other, 6301)
        executor._apply_counter_annotations(
            _ann_snap(3, _counter_ann(23, [6301], 1, 1), bf={6301: 1})
        )
        assert other.plus_one_counters == 1
        assert perm.plus_one_counters == 0  # retired, cleared

        # perm returns as a fresh stint; another unrelated counter fires. The old
        # ledger stays retired — perm is not resurrected to 2.
        _place(executor, perm, 6202)
        executor._apply_counter_annotations(
            _ann_snap(4, _counter_ann(24, [6301], 1, 1), bf={6202: 1, 6301: 1})
        )
        assert perm.plus_one_counters == 0
        assert other.plus_one_counters == 2

    def test_existing_engine_counter_not_double_counted_across_stint(
        self, executor: ReplayExecutor
    ) -> None:
        # An engine-driven counter the GRE stream also attests is set (no double
        # count) within a stint, and cleared — not carried — into the next.
        perm = _FakePermanent(2004)
        perm.plus_one_counters = 1
        perm._base_plus_one_counters = 1
        _place(executor, perm, 6401)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(25, [6401], 1, 1), bf={6401: 1})
        )
        assert perm.plus_one_counters == 1  # SET agrees, not 2

        _remove(executor, perm)
        executor._apply_counter_annotations(_ann_snap(3))
        assert perm.plus_one_counters == 0

    def test_gre_id_churn_without_zone_change_preserves_counter(
        self, executor: ReplayExecutor
    ) -> None:
        # GRE re-mints the object's instance id (churn, NOT a zone change) — the
        # engine object and its battlefield stint are unchanged, so the counter
        # is preserved (this is what aid-keying got wrong).
        perm = _FakePermanent(2006)
        _place(executor, perm, 6601)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(28, [6601], 1, 3), bf={6601: 1})
        )
        assert perm.plus_one_counters == 3

        # New GRE aid 6602 for the SAME engine object; no engine zone change.
        del executor._engine_cards[6601]
        executor._engine_cards[6602] = perm
        executor._apply_counter_annotations(_ann_snap(3, bf={6602: 1}))
        assert perm.plus_one_counters == 3  # preserved, not cleared


class TestCounterDeferral:
    """No annotation is silently consumed because correlation was temporarily
    unavailable; each affected id is tracked independently and applied
    exactly once."""

    def test_uncorrelated_battlefield_resident_late_correlation_applies(
        self, executor: ReplayExecutor
    ) -> None:
        # Valid late correlation: the engine object IS on the engine
        # battlefield during the first reconciliation pass (its epoch is
        # swept into the pendency evidence then) but not yet in _engine_cards
        # (the map is only rebuilt post-comparison). The deferred retry may
        # fold because the prior-pass observation plus an unchanged epoch
        # bracket the pendency window.
        from engine.types import Zone

        perm = _FakePermanent(3000)
        executor.players[1].zones[Zone.BATTLEFIELD].add(perm)  # present, unmapped
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(30, [7001], 1, 1), bf={7001: 1})
        )
        assert (30, 7001) in executor._pending_counter_effects
        assert (30, 7001) not in executor._applied_counter_effects
        payload = executor._pending_counter_effects[(30, 7001)]
        okey = executor._counter_key(perm)
        # Evidence observation pass 1 — the sweep that saw the object BEFORE
        # the retry; this is what licenses the deferred fold below.
        assert payload["bf_epochs"][okey] == (0, 1)
        assert payload["pending_since"] == 1

        # The post-comparison rebuild correlates the permanent; retry applies.
        executor._engine_cards[7001] = perm
        executor._apply_counter_annotations(_ann_snap(3, bf={7001: 1}))  # no repeat
        assert perm.plus_one_counters == 1
        assert (30, 7001) in executor._applied_counter_effects
        assert (30, 7001) not in executor._pending_counter_effects

    def test_candidate_created_only_on_retry_pass_cancels_unproven(
        self, executor: ReplayExecutor
    ) -> None:
        # The annotation pends with NO candidate on the engine battlefield;
        # the engine object is created (and correlated) only on the retry
        # pass. Its current epoch is then the endpoint measuring itself — not
        # proof it survived the pendency window — so the effect cancels as
        # unproven instead of folding onto the newcomer, and the missing
        # counter stays visible in comparison.
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(37, [7005], 1, 1), bf={7005: 1})
        )
        assert (37, 7005) in executor._pending_counter_effects
        payload = executor._pending_counter_effects[(37, 7005)]
        assert payload["pending_since"] == 1

        perm = _FakePermanent(3050)
        _place(executor, perm, 7005)  # created + correlated only NOW
        executor._apply_counter_annotations(_ann_snap(3, bf={7005: 1}))
        assert perm.plus_one_counters == 0
        assert (37, 7005) in executor._cancelled_counter_effects
        assert (37, 7005) not in executor._applied_counter_effects
        assert (37, 7005) not in executor._pending_counter_effects
        # First (and only) observation of the newcomer is the retry pass.
        assert payload["bf_epochs"][executor._counter_key(perm)] == (0, 2)
        [rec] = [
            r for r in executor._unresolved_counter_effects
            if r["annotation_id"] == 37
        ]
        assert "first observed after pendency began" in rec["reason"]
        assert rec["pending_since"] == 1

    def test_engine_minted_token_same_snapshot_correlated_and_countered(
        self, executor: ReplayExecutor
    ) -> None:
        # Raw replay-shaped: an engine-minted token, id-less and absent from
        # _engine_cards, is correlated by _correlate_tokens_in_group (which now
        # publishes the GRE-instance -> engine-object binding) so a same-snapshot
        # CounterAdded on the token lands via that binding.
        executor.token_map = TokenIdMap({"tokens": {"90001": {
            "card_types": ["creature"], "subtypes": ["Cat"],
            "base_power": 1, "base_toughness": 1, "colors": ["White"],
            "label": "1/1 white Cat",
        }}})
        token = _FakeToken()
        from engine.types import Zone
        executor.players[1].zones[Zone.BATTLEFIELD].add(token)  # a real bf resident
        gre_tok = GameObject(
            instance_id=7100, grp_id=90001, type="GameObjectType_Token",
            zone_id=30, owner_seat_id=1, controller_seat_id=1,
        )
        executor._correlate_tokens_in_group([gre_tok], [token])
        assert token._grp_id == 90001
        assert executor._counter_token_binding.get(7100) is token
        assert 7100 not in executor._engine_cards  # resolved via binding, not map

        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(31, [7100], 1, 1),
                      bf={7100: 1}, grp={7100: 90001})
        )
        assert token.plus_one_counters == 1

        # Persistent-slot repeat: the same-snapshot minted-token correlation
        # stays exactly-once.
        executor._apply_counter_annotations(
            _ann_snap(3, _counter_ann(31, [7100], 1, 1),
                      bf={7100: 1}, grp={7100: 90001})
        )
        assert token.plus_one_counters == 1
        assert (31, 7100) in executor._applied_counter_effects

    def test_multi_affected_ids_apply_each_once(
        self, executor: ReplayExecutor
    ) -> None:
        # One annotation with two affected ids: one correlates immediately,
        # the other later (battlefield-resident from the first sweep, so its
        # prior-pass evidence licenses the deferred fold). Each effect applies
        # exactly once; the already-handled id is not double-applied when the
        # annotation is retried.
        from engine.types import Zone

        perm_a = _FakePermanent(3100)
        _place(executor, perm_a, 7200)  # correlated now
        perm_b = _FakePermanent(3101)
        executor.players[1].zones[Zone.BATTLEFIELD].add(perm_b)  # present, unmapped
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(32, [7200, 7201], 1, 1),
                      bf={7200: 1, 7201: 1})
        )
        assert perm_a.plus_one_counters == 1
        assert (32, 7200) in executor._applied_counter_effects
        assert (32, 7201) in executor._pending_counter_effects  # not yet

        # 7201 correlates; retry applies only that effect, 7200 stays at 1.
        executor._engine_cards[7201] = perm_b
        executor._apply_counter_annotations(
            _ann_snap(3, _counter_ann(32, [7200, 7201], 1, 1),  # repeat
                      bf={7200: 1, 7201: 1})
        )
        assert perm_a.plus_one_counters == 1  # not double-applied
        assert perm_b.plus_one_counters == 1

    def test_repeated_annotation_ids_idempotent(
        self, executor: ReplayExecutor
    ) -> None:
        perm = _FakePermanent(3200)
        _place(executor, perm, 7300)
        for gsid in (2, 3, 4):  # Arena repeats the same annotation each slot
            executor._apply_counter_annotations(
                _ann_snap(gsid, _counter_ann(33, [7300], 1, 1), bf={7300: 1})
            )
        assert perm.plus_one_counters == 1

    def test_counter_removed_real_detail_shape_across_lifecycle(
        self, executor: ReplayExecutor
    ) -> None:
        # CounterRemoved uses the real parser detail shape (list-wrapped
        # counter_type / transaction_amount) and behaves correctly through a
        # blink: the removal lands, then the stint retires without carrying over.
        perm = _FakePermanent(3300)
        _place(executor, perm, 7400)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(34, [7400], 1, 3), bf={7400: 1})
        )
        executor._apply_counter_annotations(
            _ann_snap(3, _counter_ann(35, [7400], 1, 2, removed=True), bf={7400: 1})
        )
        assert perm.plus_one_counters == 1

        # Blink -> leaves the battlefield, no annotation: the 1 remaining counter
        # is retired.
        _remove(executor, perm)
        executor._apply_counter_annotations(_ann_snap(4))
        assert perm.plus_one_counters == 0


def _id_change(ann_id: int, orig: int, new: int) -> _Annotation:
    return _Annotation(
        id=ann_id, type=["AnnotationType_ObjectIdChanged"],
        details={"orig_id": [orig], "new_id": [new]},
    )


class TestCounterCanonicalAliases:
    """One semantic counter effect has ONE canonical identity across GRE
    instance-id renames: applied and cancelled state cover every rename alias,
    so a persistent-slot repeat under a renamed aid can neither double-apply
    an already folded effect nor resurrect a cancelled one. (Same-stint churn
    PROOF is engine-epoch-driven and pinned in the workspace simulate suite;
    this suite pins the identity surfaces.)"""

    def test_repeat_under_renamed_aid_is_not_a_new_effect(
        self, executor: ReplayExecutor
    ) -> None:
        perm = _FakePermanent(4000)
        _place(executor, perm, 5601)
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(40, [5601], 1, 1), bf={5601: 1})
        )
        assert perm.plus_one_counters == 1

        # GRE renames the aid; the SAME annotation id repeats under the new
        # aid. The repeat canonicalizes to the applied record — it must not
        # mint a second (annotation, aid) effect and double-apply.
        del executor._engine_cards[5601]
        executor._engine_cards[5602] = perm
        executor._apply_counter_annotations(
            _ann_snap(3, _id_change(90, 5601, 5602),
                      _counter_ann(40, [5602], 1, 1), bf={5602: 1})
        )
        assert perm.plus_one_counters == 1
        assert executor._counter_aid_alias == {5602: 5601}
        assert executor._applied_counter_effects == {(40, 5601)}
        assert not executor._pending_counter_effects
        assert not executor._cancelled_counter_effects

    def test_cancelled_effect_not_resurrected_by_aliased_repeat(
        self, executor: ReplayExecutor
    ) -> None:
        # The effect pends UNCORRELATED; its aid is renamed. With no engine
        # correlation evidence the hop cannot be proven same-stint churn, so
        # the effect cancels — and the repeat under the new aid resolves to
        # that cancelled record instead of re-enqueueing.
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(41, [5701], 1, 2), bf={5701: 1})
        )
        assert (41, 5701) in executor._pending_counter_effects

        executor._apply_counter_annotations(
            _ann_snap(3, _id_change(91, 5701, 5702), bf={5702: 1})
        )
        assert (41, 5701) in executor._cancelled_counter_effects
        assert not executor._pending_counter_effects

        perm = _FakePermanent(4001)
        _place(executor, perm, 5702)
        executor._apply_counter_annotations(
            _ann_snap(4, _counter_ann(41, [5702], 1, 2), bf={5702: 1})
        )
        assert perm.plus_one_counters == 0
        assert not executor._pending_counter_effects
        assert not executor._applied_counter_effects
        assert executor._cancelled_counter_effects == {(41, 5701)}
        assert len(executor._unresolved_counter_effects) == 1
        assert executor._unresolved_counter_effects[0]["current_aid"] == 5701

    def test_rename_chain_aliases_all_resolve_to_root(
        self, executor: ReplayExecutor
    ) -> None:
        # A rename CHAIN (blink legs in one snapshot) cancels the pending
        # effect — and BOTH hop targets alias to the root, so a repeat under
        # the final aid still hits the cancelled record.
        executor._apply_counter_annotations(
            _ann_snap(2, _counter_ann(42, [5801], 1, 1), bf={5801: 1})
        )
        executor._apply_counter_annotations(
            _ann_snap(3, _id_change(92, 5801, 5802), _id_change(93, 5802, 5803),
                      bf={5803: 1})
        )
        assert (42, 5801) in executor._cancelled_counter_effects
        assert executor._canonical_aid(5803) == 5801
        assert executor._canonical_aid(5802) == 5801

        perm = _FakePermanent(4002)
        _place(executor, perm, 5803)
        executor._apply_counter_annotations(
            _ann_snap(4, _counter_ann(42, [5803], 1, 1), bf={5803: 1})
        )
        assert perm.plus_one_counters == 0
        assert not executor._pending_counter_effects
        assert len(executor._unresolved_counter_effects) == 1
