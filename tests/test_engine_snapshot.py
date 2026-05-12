"""Tests for TODO item 6: Engine snapshot and rollback on timeout.

Verifies:
- snapshot_engine() creates a full copy of run_engine_dir at .snapshot suffix
- snapshot_engine() overwrites stale snapshots
- restore_engine_snapshot() restores deleted, modified, and new files
- restore_engine_snapshot() cleans up snapshot dir after restore
- restore_engine_snapshot() is a no-op when snapshot dir is missing
- run_card() snapshots engine before strategy, restores on timeout
- run_card() snapshots engine before strategy, restores on unexpected error
- run_card() cleans up snapshot on successful completion
- run_card() skips snapshot when run_engine_dir is None
- Timeout flow still produces a CardRunResult with timeout status
- Engine rollback does not interfere with unconditional harvest
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.agent_session import (
    AgentSession,
    restore_engine_snapshot,
    snapshot_engine,
)
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import CardRunResult, CardRunStatus


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_SPEC = {
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


def _make_config(tmp_path: Path, **overrides) -> BenchmarkConfig:
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    defaults = dict(
        name="test-bench",
        set_code="TST",
        model_name="test-model",
        model_provider="test",
        max_context=200_000,
        temperature=0.0,
        mode="blind",
        output_dir=str(output_dir),
        agent=AgentConfig(timeout_per_card=10, adapter="mock"),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


def _make_session(
    tmp_path: Path,
    run_engine_dir: Path | None = None,
    **config_overrides,
) -> AgentSession:
    config = _make_config(tmp_path, **config_overrides)
    card_dir = tmp_path / "card_data"
    card_dir.mkdir(exist_ok=True)
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
    return AgentSession(
        config=config,
        card_spec=_SAMPLE_SPEC,
        card_dir=str(card_dir),
        run_engine_dir=run_engine_dir,
        run_dir=tmp_path / "output",
    )


# ---------------------------------------------------------------------------
# Unit tests: snapshot_engine()
# ---------------------------------------------------------------------------


class TestSnapshotEngine:
    """snapshot_engine(run_engine_dir) -> Path must create a faithful copy."""

    def test_returns_path_with_snapshot_suffix(self, tmp_path: Path) -> None:
        """Returned path should be run_engine_dir.with_suffix('.snapshot')."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("class Card: pass")

        result = snapshot_engine(run_engine)

        assert result == run_engine.with_suffix(".snapshot")

    def test_snapshot_directory_exists(self, tmp_path: Path) -> None:
        """The snapshot directory should exist on disk after call."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("content")

        snapshot = snapshot_engine(run_engine)

        assert snapshot.is_dir()

    def test_copies_all_files(self, tmp_path: Path) -> None:
        """All files in the engine dir must be present in the snapshot."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("class Card: pass")
        (run_engine / "game.py").write_text("class Game: pass")
        (run_engine / "__init__.py").write_text("")

        snapshot = snapshot_engine(run_engine)

        assert (snapshot / "card.py").read_text() == "class Card: pass"
        assert (snapshot / "game.py").read_text() == "class Game: pass"
        assert (snapshot / "__init__.py").read_text() == ""

    def test_preserves_subdirectory_structure(self, tmp_path: Path) -> None:
        """Nested directories must be preserved in snapshot."""
        run_engine = tmp_path / "run_engine"
        (run_engine / "sub" / "deep").mkdir(parents=True)
        (run_engine / "sub" / "module.py").write_text("x = 1")
        (run_engine / "sub" / "deep" / "nested.py").write_text("y = 2")

        snapshot = snapshot_engine(run_engine)

        assert (snapshot / "sub" / "module.py").read_text() == "x = 1"
        assert (snapshot / "sub" / "deep" / "nested.py").read_text() == "y = 2"

    def test_overwrites_stale_snapshot(self, tmp_path: Path) -> None:
        """If a .snapshot already exists, it must be replaced with current state."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("v1")

        snapshot_engine(run_engine)

        # Modify engine
        (run_engine / "card.py").write_text("v2")

        snapshot = snapshot_engine(run_engine)

        assert (snapshot / "card.py").read_text() == "v2"

    def test_snapshot_is_independent_copy(self, tmp_path: Path) -> None:
        """Modifying engine after snapshot must not affect snapshot contents."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original")

        snapshot = snapshot_engine(run_engine)

        # Mutate the original
        (run_engine / "card.py").write_text("changed")
        (run_engine / "new.py").write_text("added")

        # Snapshot should be unchanged
        assert (snapshot / "card.py").read_text() == "original"
        assert not (snapshot / "new.py").exists()


# ---------------------------------------------------------------------------
# Unit tests: restore_engine_snapshot()
# ---------------------------------------------------------------------------


class TestRestoreEngineSnapshot:
    """restore_engine_snapshot must faithfully restore run_engine_dir."""

    def test_restores_modified_file(self, tmp_path: Path) -> None:
        """A file modified after snapshot must be restored to original content."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original")

        snapshot = snapshot_engine(run_engine)

        (run_engine / "card.py").write_text("corrupted")

        restore_engine_snapshot(run_engine, snapshot)

        assert (run_engine / "card.py").read_text() == "original"

    def test_restores_deleted_file(self, tmp_path: Path) -> None:
        """A file deleted after snapshot must be restored."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("important")

        snapshot = snapshot_engine(run_engine)

        (run_engine / "card.py").unlink()

        restore_engine_snapshot(run_engine, snapshot)

        assert (run_engine / "card.py").read_text() == "important"

    def test_removes_new_files_not_in_snapshot(self, tmp_path: Path) -> None:
        """Files added after snapshot must be removed on restore."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original")

        snapshot = snapshot_engine(run_engine)

        (run_engine / "injected.py").write_text("bad code")

        restore_engine_snapshot(run_engine, snapshot)

        assert not (run_engine / "injected.py").exists()

    def test_cleans_up_snapshot_dir_after_restore(self, tmp_path: Path) -> None:
        """Snapshot directory must be deleted after a successful restore."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original")

        snapshot = snapshot_engine(run_engine)
        assert snapshot.exists()

        restore_engine_snapshot(run_engine, snapshot)

        assert not snapshot.exists()

    def test_noop_when_snapshot_missing(self, tmp_path: Path) -> None:
        """When snapshot dir does not exist, engine must be left unchanged."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("current")

        missing_snapshot = tmp_path / "run_engine.snapshot"

        # Should not raise
        restore_engine_snapshot(run_engine, missing_snapshot)

        assert (run_engine / "card.py").read_text() == "current"

    def test_restores_subdirectory_structure(self, tmp_path: Path) -> None:
        """Subdirectories must be restored faithfully."""
        run_engine = tmp_path / "run_engine"
        (run_engine / "sub").mkdir(parents=True)
        (run_engine / "sub" / "mod.py").write_text("x = 1")

        snapshot = snapshot_engine(run_engine)

        # Corrupt: delete subdir, add new file
        import shutil
        shutil.rmtree(run_engine / "sub")
        (run_engine / "bad.py").write_text("bad")

        restore_engine_snapshot(run_engine, snapshot)

        assert (run_engine / "sub" / "mod.py").read_text() == "x = 1"
        assert not (run_engine / "bad.py").exists()


# ---------------------------------------------------------------------------
# Integration: run_card() with engine snapshot/rollback
# ---------------------------------------------------------------------------


class TestRunCardEngineRollbackOnTimeout:
    """run_card() must snapshot before strategy and restore on timeout."""

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_engine_restored_on_timeout(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """When strategy raises TimeoutExpired, engine must be rolled back."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original_content")
        (run_engine / "helper.py").write_text("helper_original")

        session = _make_session(tmp_path, run_engine_dir=run_engine)

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def _timeout_side_effect(*args, **kwargs):
            # Simulate agent corrupting engine before timeout
            (run_engine / "card.py").write_text("corrupted_by_agent")
            (run_engine / "injected.py").write_text("bad new file")
            (run_engine / "helper.py").unlink()
            raise subprocess.TimeoutExpired(cmd="agent", timeout=10)

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.side_effect = _timeout_side_effect
            mock_gs.return_value = mock_strategy

            result = session.run_card()

        # Engine fully restored
        assert (run_engine / "card.py").read_text() == "original_content"
        assert (run_engine / "helper.py").read_text() == "helper_original"
        assert not (run_engine / "injected.py").exists()
        # Snapshot cleaned up
        assert not run_engine.with_suffix(".snapshot").exists()
        # Result is timeout
        assert result.status == CardRunStatus.timeout

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_engine_restored_on_unexpected_error(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """When strategy raises an unexpected exception, engine must be rolled back."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("pre_error")

        session = _make_session(tmp_path, run_engine_dir=run_engine)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def _error_side_effect(*args, **kwargs):
            (run_engine / "card.py").write_text("corrupted_by_crash")
            raise RuntimeError("unexpected adapter failure")

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.side_effect = _error_side_effect
            mock_gs.return_value = mock_strategy

            with pytest.raises(RuntimeError, match="unexpected adapter failure"):
                session.run_card()

        # Engine restored despite exception
        assert (run_engine / "card.py").read_text() == "pre_error"
        assert not run_engine.with_suffix(".snapshot").exists()


class TestRunCardEngineSnapshotCleanup:
    """run_card() must clean up snapshot on successful completion."""

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_snapshot_deleted_on_success(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """On successful strategy completion, snapshot dir must be deleted."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original")

        session = _make_session(tmp_path, run_engine_dir=run_engine)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.return_value = CardRunResult(
                status=CardRunStatus.completed,
                files_written=["card_impl.py"],
                runtime_ms=200,
            )
            mock_gs.return_value = mock_strategy

            result = session.run_card()

        assert result.status == CardRunStatus.completed
        # Snapshot cleaned up
        assert not run_engine.with_suffix(".snapshot").exists()
        # Engine NOT rolled back — agent changes are preserved
        assert (run_engine / "card.py").read_text() == "original"

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_engine_changes_preserved_on_success(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """On success, agent modifications to engine must be preserved (not rolled back)."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("before")

        session = _make_session(tmp_path, run_engine_dir=run_engine)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def _success_with_engine_changes(*args, **kwargs):
            # Agent modifies engine during successful run
            (run_engine / "card.py").write_text("improved_by_agent")
            return CardRunResult(
                status=CardRunStatus.completed,
                files_written=["card_impl.py"],
                runtime_ms=300,
            )

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.side_effect = _success_with_engine_changes
            mock_gs.return_value = mock_strategy

            result = session.run_card()

        assert result.status == CardRunStatus.completed
        # Engine changes persisted
        assert (run_engine / "card.py").read_text() == "improved_by_agent"
        # No snapshot left behind
        assert not run_engine.with_suffix(".snapshot").exists()


class TestRunCardNoEngineDir:
    """run_card() must work fine when no run_engine_dir is set."""

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_no_snapshot_when_no_engine_dir(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """When run_engine_dir is None, no snapshot should be created."""
        session = _make_session(tmp_path, run_engine_dir=None)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.return_value = CardRunResult(
                status=CardRunStatus.completed,
                files_written=["card_impl.py"],
                runtime_ms=100,
            )
            mock_gs.return_value = mock_strategy

            result = session.run_card()

        assert result.status == CardRunStatus.completed


# ---------------------------------------------------------------------------
# Functions are importable from agent_session module
# ---------------------------------------------------------------------------


class TestSnapshotFunctionsImportable:
    """snapshot_engine and restore_engine_snapshot must be public API."""

    def test_snapshot_engine_importable(self) -> None:
        from silverquillm.agent_session import snapshot_engine
        assert callable(snapshot_engine)

    def test_restore_engine_snapshot_importable(self) -> None:
        from silverquillm.agent_session import restore_engine_snapshot
        assert callable(restore_engine_snapshot)

    def test_functions_in_all(self) -> None:
        import silverquillm.agent_session as mod
        assert "snapshot_engine" in mod.__all__
        assert "restore_engine_snapshot" in mod.__all__

