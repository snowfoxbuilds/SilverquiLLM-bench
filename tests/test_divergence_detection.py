"""Tests for divergence detection and reporting (validation.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.replay.executor import ReplayExecutor, StateMismatch, StepResult
from silverquillm.replay.types import (
    GameSnapshot,
    GameObject,
    PlayerInfo,
    ReplayAction,
    ReplayGame,
    TurnInfo,
    Zone as ReplayZone,
)
from silverquillm.replay.validation import (
    Divergence,
    DivergenceType,
    ValidatingExecutor,
    ValidationReport,
    validate_replay,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOUNTAIN_GRP = 95197
PLAINS_GRP = 95191
GOBLIN_GRP = 12345
CARD_ID_MAP = {MOUNTAIN_GRP: "Mountain", PLAINS_GRP: "Plains", GOBLIN_GRP: "Goblin Guide"}


def _make_snapshot(
    game_state_id: int = 1,
    actions: list[ReplayAction] | None = None,
    p1_life: int = 20,
    p2_life: int = 20,
) -> GameSnapshot:
    """Build a minimal GameSnapshot."""
    snap = GameSnapshot(game_state_id=game_state_id)
    snap.players = {
        1: PlayerInfo(seat_id=1, life_total=p1_life),
        2: PlayerInfo(seat_id=2, life_total=p2_life),
    }
    snap.zones[10] = ReplayZone(zone_id=10, type="ZoneType_Hand", owner_seat_id=1, object_instance_ids=[101])
    snap.zones[20] = ReplayZone(zone_id=20, type="ZoneType_Hand", owner_seat_id=2, object_instance_ids=[201])
    snap.game_objects[101] = GameObject(
        instance_id=101, grp_id=MOUNTAIN_GRP, type="GameObjectType_Card",
        zone_id=10, owner_seat_id=1,
    )
    snap.game_objects[201] = GameObject(
        instance_id=201, grp_id=PLAINS_GRP, type="GameObjectType_Card",
        zone_id=20, owner_seat_id=2,
    )
    snap.actions = actions or []
    return snap


def _make_mock_executor(
    snapshots: list[GameSnapshot] | None = None,
    card_id_map: dict[int, str] | None = None,
    registry: object | None = None,
) -> MagicMock:
    """Create a mock ReplayExecutor with the fields ValidatingExecutor reads."""
    mock = MagicMock(spec=ReplayExecutor)
    mock.card_id_map = card_id_map or CARD_ID_MAP
    mock.registry = registry
    mock._initialized = True
    replay = MagicMock()
    replay.snapshots = snapshots or []
    mock.replay = replay
    return mock


def _make_divergence(
    game_state_id: int = 1,
    div_type: DivergenceType = DivergenceType.STATE_MISMATCH,
    description: str = "test divergence",
    grp_ids: list[int] | None = None,
    expected: object = None,
    actual: object = None,
) -> Divergence:
    return Divergence(
        game_state_id=game_state_id,
        divergence_type=div_type,
        description=description,
        expected_state=expected,
        actual_state=actual,
        involved_grp_ids=grp_ids or [],
    )


# ---------------------------------------------------------------------------
# DivergenceType enum
# ---------------------------------------------------------------------------

class TestDivergenceType:
    """Tests for the DivergenceType enum values."""

    def test_has_missing_card(self) -> None:
        assert DivergenceType.MISSING_CARD.value == "MISSING_CARD"

    def test_has_illegal_action(self) -> None:
        assert DivergenceType.ILLEGAL_ACTION.value == "ILLEGAL_ACTION"

    def test_has_state_mismatch(self) -> None:
        assert DivergenceType.STATE_MISMATCH.value == "STATE_MISMATCH"

    def test_has_engine_error(self) -> None:
        assert DivergenceType.ENGINE_ERROR.value == "ENGINE_ERROR"

    def test_has_query_unanswered(self) -> None:
        # MSH Player Query protocol: no replay-derived intent matched a query.
        assert DivergenceType.QUERY_UNANSWERED.value == "QUERY_UNANSWERED"

    def test_has_protocol_error(self) -> None:
        # MSH Player Query protocol: engine-side boundary-validation failure.
        assert DivergenceType.PROTOCOL_ERROR.value == "PROTOCOL_ERROR"

    def test_exactly_six_members(self) -> None:
        # Four V1 divergence types + the two MSH Player Query types.
        assert len(DivergenceType) == 6


# ---------------------------------------------------------------------------
# Divergence dataclass
# ---------------------------------------------------------------------------

class TestDivergence:
    """Tests for the Divergence dataclass."""

    def test_creation_with_required_fields(self) -> None:
        d = Divergence(
            game_state_id=42,
            divergence_type=DivergenceType.STATE_MISMATCH,
            description="Life mismatch",
        )
        assert d.game_state_id == 42
        assert d.divergence_type == DivergenceType.STATE_MISMATCH
        assert d.description == "Life mismatch"

    def test_severity_defaults_to_divergence_type(self) -> None:
        d = Divergence(
            game_state_id=1,
            divergence_type=DivergenceType.ENGINE_ERROR,
            description="boom",
        )
        assert d.severity == DivergenceType.ENGINE_ERROR

    def test_expected_and_actual_state_stored(self) -> None:
        d = Divergence(
            game_state_id=1,
            divergence_type=DivergenceType.STATE_MISMATCH,
            description="life",
            expected_state=20,
            actual_state=18,
        )
        assert d.expected_state == 20
        assert d.actual_state == 18

    def test_action_stored(self) -> None:
        action = ReplayAction(action_type="spell_cast", grp_id=GOBLIN_GRP)
        d = Divergence(
            game_state_id=1,
            divergence_type=DivergenceType.ILLEGAL_ACTION,
            description="rejected",
            action=action,
        )
        assert d.action is action

    def test_involved_grp_ids_stored(self) -> None:
        d = Divergence(
            game_state_id=1,
            divergence_type=DivergenceType.MISSING_CARD,
            description="missing",
            involved_grp_ids=[GOBLIN_GRP, MOUNTAIN_GRP],
        )
        assert d.involved_grp_ids == [GOBLIN_GRP, MOUNTAIN_GRP]

    def test_str_contains_type_and_id(self) -> None:
        d = Divergence(
            game_state_id=5,
            divergence_type=DivergenceType.STATE_MISMATCH,
            description="life mismatch",
        )
        s = str(d)
        assert "STATE_MISMATCH" in s
        assert "5" in s

    def test_str_contains_grp_ids_when_present(self) -> None:
        d = Divergence(
            game_state_id=1,
            divergence_type=DivergenceType.MISSING_CARD,
            description="missing card",
            involved_grp_ids=[GOBLIN_GRP],
        )
        s = str(d)
        assert str(GOBLIN_GRP) in s


# ---------------------------------------------------------------------------
# ValidationReport — no divergences (clean run)
# ---------------------------------------------------------------------------

class TestValidationReportClean:
    """Tests for a clean ValidationReport (no divergences)."""

    def test_zero_divergences(self) -> None:
        report = ValidationReport(total_snapshots=10, successful_comparisons=10)
        assert report.divergence_count == 0

    def test_divergences_by_type_empty(self) -> None:
        report = ValidationReport(total_snapshots=5, successful_comparisons=5)
        assert report.divergences_by_type == {}

    def test_per_card_divergence_rates_empty(self) -> None:
        report = ValidationReport(total_snapshots=5, successful_comparisons=5)
        assert report.per_card_divergence_rates == {}

    def test_first_divergence_point_is_none(self) -> None:
        report = ValidationReport(total_snapshots=5, successful_comparisons=5)
        assert report.first_divergence_point is None

    def test_summary_includes_snapshot_count(self) -> None:
        report = ValidationReport(total_snapshots=10, successful_comparisons=10)
        s = report.summary()
        assert "10" in s
        assert "Divergences: 0" in s


# ---------------------------------------------------------------------------
# ValidationReport — with divergences
# ---------------------------------------------------------------------------

class TestValidationReportWithDivergences:
    """Tests for ValidationReport computed properties with mixed divergences."""

    @pytest.fixture
    def mixed_report(self) -> ValidationReport:
        """Report with several divergence types."""
        divs = [
            _make_divergence(game_state_id=1, div_type=DivergenceType.MISSING_CARD, grp_ids=[GOBLIN_GRP]),
            _make_divergence(game_state_id=2, div_type=DivergenceType.STATE_MISMATCH, grp_ids=[MOUNTAIN_GRP]),
            _make_divergence(game_state_id=3, div_type=DivergenceType.STATE_MISMATCH, grp_ids=[MOUNTAIN_GRP]),
            _make_divergence(game_state_id=4, div_type=DivergenceType.ENGINE_ERROR, grp_ids=[PLAINS_GRP]),
            _make_divergence(game_state_id=5, div_type=DivergenceType.ILLEGAL_ACTION, grp_ids=[GOBLIN_GRP]),
        ]
        return ValidationReport(
            total_snapshots=10,
            successful_comparisons=5,
            divergences=divs,
            card_appearances={GOBLIN_GRP: 4, MOUNTAIN_GRP: 4, PLAINS_GRP: 2},
        )

    def test_divergence_count(self, mixed_report: ValidationReport) -> None:
        assert mixed_report.divergence_count == 5

    def test_divergences_by_type_counts(self, mixed_report: ValidationReport) -> None:
        by_type = mixed_report.divergences_by_type
        assert by_type[DivergenceType.MISSING_CARD] == 1
        assert by_type[DivergenceType.STATE_MISMATCH] == 2
        assert by_type[DivergenceType.ENGINE_ERROR] == 1
        assert by_type[DivergenceType.ILLEGAL_ACTION] == 1

    def test_per_card_divergence_rates(self, mixed_report: ValidationReport) -> None:
        rates = mixed_report.per_card_divergence_rates
        # Rates are ratios: divergences involving card / total appearances of card.
        # In mixed_report fixture: card_appearances gives each card some appearances.
        # GOBLIN_GRP: 2 divergences / 4 appearances = 0.5
        assert rates[GOBLIN_GRP] == pytest.approx(0.5)
        # MOUNTAIN_GRP: 2 divergences / 4 appearances = 0.5
        assert rates[MOUNTAIN_GRP] == pytest.approx(0.5)
        # PLAINS_GRP: 1 divergence / 2 appearances = 0.5
        assert rates[PLAINS_GRP] == pytest.approx(0.5)

    def test_first_divergence_point_is_first_added(self, mixed_report: ValidationReport) -> None:
        first = mixed_report.first_divergence_point
        assert first is not None
        assert first.game_state_id == 1
        assert first.divergence_type == DivergenceType.MISSING_CARD

    def test_summary_contains_type_counts(self, mixed_report: ValidationReport) -> None:
        s = mixed_report.summary()
        assert "STATE_MISMATCH" in s
        assert "MISSING_CARD" in s
        assert "ENGINE_ERROR" in s

    def test_summary_contains_top_cards(self, mixed_report: ValidationReport) -> None:
        s = mixed_report.summary()
        assert "Top divergent cards" in s
        assert str(GOBLIN_GRP) in s

    def test_summary_contains_first_divergence(self, mixed_report: ValidationReport) -> None:
        s = mixed_report.summary()
        assert "First divergence" in s


# ---------------------------------------------------------------------------
# Multiple divergences on same card
# ---------------------------------------------------------------------------

class TestMultipleDivergencesSameCard:
    """Edge case: several divergences involving the same grpId."""

    def test_per_card_rate_accumulates(self) -> None:
        divs = [
            _make_divergence(grp_ids=[GOBLIN_GRP]),
            _make_divergence(grp_ids=[GOBLIN_GRP]),
            _make_divergence(grp_ids=[GOBLIN_GRP]),
        ]
        report = ValidationReport(
            total_snapshots=5,
            successful_comparisons=2,
            divergences=divs,
            card_appearances={GOBLIN_GRP: 5},
        )
        # 3 divergences / 5 appearances = 0.6
        assert report.per_card_divergence_rates[GOBLIN_GRP] == pytest.approx(0.6)

    def test_divergence_with_multiple_grp_ids(self) -> None:
        """A single divergence can involve multiple grpIds."""
        div = _make_divergence(grp_ids=[GOBLIN_GRP, MOUNTAIN_GRP])
        report = ValidationReport(
            total_snapshots=1,
            successful_comparisons=0,
            divergences=[div],
            card_appearances={GOBLIN_GRP: 1, MOUNTAIN_GRP: 2},
        )
        rates = report.per_card_divergence_rates
        # GOBLIN_GRP: 1/1 = 1.0
        assert rates[GOBLIN_GRP] == pytest.approx(1.0)
        # MOUNTAIN_GRP: 1/2 = 0.5
        assert rates[MOUNTAIN_GRP] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# ValidatingExecutor — MISSING_CARD detection
# ---------------------------------------------------------------------------

class TestValidatingExecutorMissingCard:
    """Tests for MISSING_CARD detection when card is not in registry."""

    def test_missing_card_detected_when_not_in_registry(self) -> None:
        """An action referencing a grpId whose card name is not in the registry should produce MISSING_CARD."""
        action = ReplayAction(action_type="spell_cast", grp_id=GOBLIN_GRP)
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2, actions=[action])

        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        # Registry that does NOT contain "Goblin Guide"
        registry = {"Mountain": True, "Plains": True}
        mock_exec.registry = registry

        # execute_step returns a clean result
        mock_exec.execute_step.return_value = StepResult(snapshot_id=2, mismatches=[])

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        validator.execute_step(snap_prev, snap_curr)

        report = validator.report()
        assert report.divergence_count >= 1
        missing = [d for d in report.divergences if d.divergence_type == DivergenceType.MISSING_CARD]
        assert len(missing) >= 1
        assert missing[0].involved_grp_ids == [GOBLIN_GRP]

    def test_no_missing_card_when_in_registry(self) -> None:
        """A card that IS in the registry should NOT produce MISSING_CARD."""
        action = ReplayAction(action_type="land_play", grp_id=MOUNTAIN_GRP)
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2, actions=[action])

        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        registry = {"Mountain": True, "Plains": True, "Goblin Guide": True}
        mock_exec.registry = registry

        mock_exec.execute_step.return_value = StepResult(snapshot_id=2, mismatches=[])

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        validator.execute_step(snap_prev, snap_curr)

        report = validator.report()
        missing = [d for d in report.divergences if d.divergence_type == DivergenceType.MISSING_CARD]
        assert len(missing) == 0

    def test_no_missing_card_when_registry_is_none(self) -> None:
        """When there is no registry, MISSING_CARD checks are skipped."""
        action = ReplayAction(action_type="spell_cast", grp_id=GOBLIN_GRP)
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2, actions=[action])

        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None

        mock_exec.execute_step.return_value = StepResult(snapshot_id=2, mismatches=[])

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        validator.execute_step(snap_prev, snap_curr)

        report = validator.report()
        missing = [d for d in report.divergences if d.divergence_type == DivergenceType.MISSING_CARD]
        assert len(missing) == 0


# ---------------------------------------------------------------------------
# ValidatingExecutor — STATE_MISMATCH
# ---------------------------------------------------------------------------

class TestValidatingExecutorStateMismatch:
    """Tests for STATE_MISMATCH when engine processes action but state differs."""

    def test_state_mismatch_from_life_total_diff(self) -> None:
        """A life total mismatch (engine!=snapshot) should produce STATE_MISMATCH."""
        action = ReplayAction(action_type="spell_cast", grp_id=MOUNTAIN_GRP)
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2, actions=[action])

        mismatch = StateMismatch(
            category="life_total",
            description="Player 1 life mismatch",
            engine_value=18,
            snapshot_value=20,
            seat_id=1,
        )
        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.return_value = StepResult(
            snapshot_id=2, mismatches=[mismatch],
        )

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        validator.execute_step(snap_prev, snap_curr)

        report = validator.report()
        sm_divs = [d for d in report.divergences if d.divergence_type == DivergenceType.STATE_MISMATCH]
        assert len(sm_divs) >= 1
        assert sm_divs[0].expected_state == 20
        assert sm_divs[0].actual_state == 18

    def test_state_mismatch_not_counted_as_successful(self) -> None:
        """Steps with mismatches should NOT be counted as successful."""
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2)

        mismatch = StateMismatch(category="zone_contents", description="zone diff")
        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.return_value = StepResult(
            snapshot_id=2, mismatches=[mismatch],
        )

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        validator.execute_step(snap_prev, snap_curr)

        report = validator.report()
        assert report.successful_comparisons == 0


# ---------------------------------------------------------------------------
# ValidatingExecutor — ENGINE_ERROR
# ---------------------------------------------------------------------------

class TestValidatingExecutorEngineError:
    """Tests for ENGINE_ERROR when executor raises an unhandled exception."""

    def test_engine_error_on_exception(self) -> None:
        """If the underlying executor raises, an ENGINE_ERROR divergence is recorded."""
        action = ReplayAction(action_type="spell_cast", grp_id=GOBLIN_GRP)
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2, actions=[action])

        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.side_effect = RuntimeError("segfault in engine")

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        result = validator.execute_step(snap_prev, snap_curr)

        assert result.success is False
        report = validator.report()
        engine_errs = [d for d in report.divergences if d.divergence_type == DivergenceType.ENGINE_ERROR]
        assert len(engine_errs) == 1
        assert "RuntimeError" in engine_errs[0].description
        assert GOBLIN_GRP in engine_errs[0].involved_grp_ids

    def test_engine_error_does_not_propagate(self) -> None:
        """ENGINE_ERROR should be caught — execute_step should NOT raise."""
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2, actions=[
            ReplayAction(action_type="land_play", grp_id=MOUNTAIN_GRP),
        ])

        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.side_effect = ValueError("unexpected None")

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        # Should not raise
        result = validator.execute_step(snap_prev, snap_curr)
        assert isinstance(result, StepResult)


# ---------------------------------------------------------------------------
# ValidatingExecutor — ILLEGAL_ACTION
# ---------------------------------------------------------------------------

class TestValidatingExecutorIllegalAction:
    """Tests for ILLEGAL_ACTION when engine rejects an action that GRE allowed."""

    def test_illegal_action_from_rejected_mismatch(self) -> None:
        """A mismatch with 'rejected' in description should be classified as ILLEGAL_ACTION."""
        action = ReplayAction(action_type="spell_cast", grp_id=GOBLIN_GRP)
        snap_prev = _make_snapshot(game_state_id=1)
        snap_curr = _make_snapshot(game_state_id=2, actions=[action])

        mismatch = StateMismatch(
            category="zone_contents",
            description="Action rejected by engine: card cannot be played",
            engine_value=None,
            snapshot_value="battlefield",
        )
        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.return_value = StepResult(
            snapshot_id=2, mismatches=[mismatch],
        )

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        validator.execute_step(snap_prev, snap_curr)

        report = validator.report()
        illegal = [d for d in report.divergences if d.divergence_type == DivergenceType.ILLEGAL_ACTION]
        assert len(illegal) >= 1


# ---------------------------------------------------------------------------
# ValidatingExecutor — clean run (all succeed)
# ---------------------------------------------------------------------------

class TestValidatingExecutorCleanRun:
    """Tests for a clean run where all actions succeed with no divergences."""

    def test_all_steps_successful(self) -> None:
        snaps = [_make_snapshot(game_state_id=i) for i in range(1, 4)]

        mock_exec = _make_mock_executor(snapshots=snaps, card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.return_value = StepResult(snapshot_id=0, mismatches=[])

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)

        for i in range(1, len(snaps)):
            validator.execute_step(snaps[i - 1], snaps[i])

        report = validator.report()
        assert report.total_snapshots == 2
        assert report.successful_comparisons == 2
        assert report.divergence_count == 0


# ---------------------------------------------------------------------------
# ValidatingExecutor — execute_all
# ---------------------------------------------------------------------------

class TestValidatingExecutorExecuteAll:
    """Tests for execute_all convenience method."""

    def test_execute_all_processes_all_transitions(self) -> None:
        snaps = [_make_snapshot(game_state_id=i) for i in range(1, 5)]

        mock_exec = _make_mock_executor(snapshots=snaps, card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.return_value = StepResult(snapshot_id=0, mismatches=[])

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        results = validator.execute_all()

        # 4 snapshots => 3 transitions
        assert len(results) == 3

    def test_execute_all_empty_replay(self) -> None:
        mock_exec = _make_mock_executor(snapshots=[], card_id_map=CARD_ID_MAP)
        mock_exec.registry = None

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        results = validator.execute_all()
        assert results == []

        report = validator.report()
        assert report.total_snapshots == 0
        assert report.divergence_count == 0

    def test_execute_all_single_snapshot(self) -> None:
        """A single snapshot means no transitions."""
        snaps = [_make_snapshot(game_state_id=1)]

        mock_exec = _make_mock_executor(snapshots=snaps, card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec._initialized = False  # Force auto-init path

        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        results = validator.execute_all()
        assert results == []


# ---------------------------------------------------------------------------
# ValidatingExecutor — report() method
# ---------------------------------------------------------------------------

class TestValidatingExecutorReport:
    """Tests for the report() method."""

    def test_report_returns_validation_report(self) -> None:
        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)
        report = validator.report()
        assert isinstance(report, ValidationReport)

    def test_report_reflects_recorded_divergences(self) -> None:
        mock_exec = _make_mock_executor(card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        validator = ValidatingExecutor(mock_exec, card_id_map=CARD_ID_MAP)

        div = _make_divergence(div_type=DivergenceType.ENGINE_ERROR)
        validator.record_divergence(div)

        report = validator.report()
        assert report.divergence_count == 1
        assert report.divergences[0].divergence_type == DivergenceType.ENGINE_ERROR


# ---------------------------------------------------------------------------
# validate_replay() convenience function
# ---------------------------------------------------------------------------

class TestValidateReplay:
    """Tests for the validate_replay() top-level convenience function."""

    def test_returns_validation_report(self) -> None:
        snaps = [_make_snapshot(game_state_id=i) for i in range(1, 4)]

        mock_exec = _make_mock_executor(snapshots=snaps, card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec.execute_step.return_value = StepResult(snapshot_id=0, mismatches=[])
        mock_exec._initialized = False

        report = validate_replay(mock_exec, card_id_map=CARD_ID_MAP)
        assert isinstance(report, ValidationReport)

    def test_captures_divergences(self) -> None:
        """validate_replay should include any divergences produced during execution."""
        snaps = [_make_snapshot(game_state_id=1), _make_snapshot(game_state_id=2)]

        mock_exec = _make_mock_executor(snapshots=snaps, card_id_map=CARD_ID_MAP)
        mock_exec.registry = None
        mock_exec._initialized = False
        mock_exec.execute_step.side_effect = RuntimeError("boom")

        report = validate_replay(mock_exec, card_id_map=CARD_ID_MAP)
        assert report.divergence_count >= 1
        engine_errs = [d for d in report.divergences if d.divergence_type == DivergenceType.ENGINE_ERROR]
        assert len(engine_errs) >= 1

    def test_empty_replay_returns_clean_report(self) -> None:
        mock_exec = _make_mock_executor(snapshots=[], card_id_map=CARD_ID_MAP)
        mock_exec.registry = None

        report = validate_replay(mock_exec, card_id_map=CARD_ID_MAP)
        assert report.divergence_count == 0
        assert report.total_snapshots == 0
