"""Tests for TODO item 16: Persistent engine per run.

Verifies:
- engine/ removed from _PROTECTED_DIRS
- Engine files in workspace are writable
- init_run_engine() creates run-level engine directory
- Card workspace gets writable copy of run engine
- commit_engine_changes() merges changes back
- commit_engine_changes() handles new files and deletions
- save_engine_final() copies final state to output
- Sequential cards see engine changes from prior cards
- Edge cases: empty engine dir, no changes
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.agent_session import (
    AgentSession,
    _PROTECTED_DIRS,
    commit_engine_changes,
    init_run_engine,
    save_engine_final,
)
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="FDN",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        agent=AgentConfig(
            max_test_rounds=3,
            timeout_per_card=300,
        ),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


_SAMPLE_SPEC = {
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


@pytest.fixture()
def config():
    return _make_config()


@pytest.fixture()
def fake_card_dir(tmp_path):
    card_dir = tmp_path / "card_data"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
    return card_dir


# ---------------------------------------------------------------------------
# 1. engine/ is NOT in _PROTECTED_DIRS
# ---------------------------------------------------------------------------

class TestProtectedDirs:
    def test_engine_not_in_protected_dirs(self):
        assert "engine" not in _PROTECTED_DIRS
        # Also check that "engine/" variant isn't present
        assert all("engine" not in d for d in _PROTECTED_DIRS)


# ---------------------------------------------------------------------------
# 2. Engine files in workspace are writable
# ---------------------------------------------------------------------------

class TestEngineWritable:
    def test_engine_files_are_writable_in_workspace(self, config, fake_card_dir, tmp_path):
        """Engine files copied to workspace should be writable (not read-only)."""
        # Create a fake run engine dir with a file
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("# card module")

        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(fake_card_dir),
            run_engine_dir=run_engine,
        )
        mock_adapter = MagicMock()
        try:
            with patch.object(session, "_get_adapter", return_value=mock_adapter):
                session.setup_workspace()
            engine_file = session.workspace / "engine" / "card.py"
            assert engine_file.exists()
            # Check file is writable by owner
            file_stat = engine_file.stat()
            assert file_stat.st_mode & stat.S_IWUSR, "Engine file should be writable"
        finally:
            session.cleanup()


# ---------------------------------------------------------------------------
# 3. init_run_engine() creates run-level engine directory
# ---------------------------------------------------------------------------

class TestInitRunEngine:
    def test_creates_run_engine_directory(self, tmp_path):
        """init_run_engine should create a run_engine/ dir under output_dir."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        result = init_run_engine(output_dir)
        assert result == output_dir / "run_engine"
        assert result.is_dir()

    def test_copies_repo_engine_contents(self, tmp_path):
        """If repo engine/ exists, its contents should be in run_engine."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        result = init_run_engine(output_dir)
        # The repo has an engine/ directory, so run_engine should have files
        repo_engine = Path(__file__).resolve().parent.parent / "engine"
        if repo_engine.exists() and any(repo_engine.iterdir()):
            assert any(result.iterdir()), "run_engine should contain files from repo engine/"

    def test_overwrites_existing_run_engine(self, tmp_path):
        """Calling init_run_engine twice should replace the previous one."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        first = init_run_engine(output_dir)
        # Add a marker file
        (first / "marker.txt").write_text("old")
        # Re-init
        second = init_run_engine(output_dir)
        assert second == first
        # marker should be gone (replaced by fresh copy from repo)
        assert not (second / "marker.txt").exists()


# ---------------------------------------------------------------------------
# 4. Card workspace gets writable copy of run engine
# ---------------------------------------------------------------------------

class TestWorkspaceEngineFromRunEngine:
    def test_workspace_uses_run_engine_dir(self, config, fake_card_dir, tmp_path):
        """When run_engine_dir is set, workspace engine/ should come from it."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "custom_module.py").write_text("# custom")

        session = AgentSession(
            config=config,
            card_spec=_SAMPLE_SPEC,
            card_dir=str(fake_card_dir),
            run_engine_dir=run_engine,
        )
        mock_adapter = MagicMock()
        try:
            with patch.object(session, "_get_adapter", return_value=mock_adapter):
                session.setup_workspace()
            assert (session.workspace / "engine" / "custom_module.py").exists()
            content = (session.workspace / "engine" / "custom_module.py").read_text()
            assert content == "# custom"
        finally:
            session.cleanup()


# ---------------------------------------------------------------------------
# 5. commit_engine_changes() merges modified files back
# ---------------------------------------------------------------------------

class TestCommitEngineChanges:
    def test_modified_file_committed(self, tmp_path):
        """Modified engine file in workspace should be copied back."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        engine_ws = workspace / "engine"
        engine_ws.mkdir()
        (engine_ws / "card.py").write_text("modified")

        updated = commit_engine_changes(workspace, run_engine)
        assert "card.py" in updated
        assert (run_engine / "card.py").read_text() == "modified"

    def test_no_changes_returns_empty(self, tmp_path):
        """When nothing changed, commit should return empty list."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("same")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        engine_ws = workspace / "engine"
        engine_ws.mkdir()
        (engine_ws / "card.py").write_text("same")

        updated = commit_engine_changes(workspace, run_engine)
        assert updated == []

    def test_no_engine_dir_in_workspace(self, tmp_path):
        """If workspace has no engine/, commit returns empty list."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        updated = commit_engine_changes(workspace, run_engine)
        assert updated == []


# ---------------------------------------------------------------------------
# 6. commit_engine_changes() handles new files
# ---------------------------------------------------------------------------

class TestCommitNewFiles:
    def test_new_file_added_by_agent(self, tmp_path):
        """New file in workspace engine/ should be committed to run engine."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()

        workspace = tmp_path / "workspace"
        engine_ws = workspace / "engine"
        engine_ws.mkdir(parents=True)
        (engine_ws / "new_module.py").write_text("# new")

        updated = commit_engine_changes(workspace, run_engine)
        assert "new_module.py" in updated
        assert (run_engine / "new_module.py").read_text() == "# new"

    def test_new_file_in_subdirectory(self, tmp_path):
        """New file in a subdirectory should be committed."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()

        workspace = tmp_path / "workspace"
        engine_ws = workspace / "engine" / "subdir"
        engine_ws.mkdir(parents=True)
        (engine_ws / "helper.py").write_text("# helper")

        updated = commit_engine_changes(workspace, run_engine)
        # Check relative path includes subdir
        assert any("helper.py" in u for u in updated)
        assert (run_engine / "subdir" / "helper.py").read_text() == "# helper"


# ---------------------------------------------------------------------------
# 7. commit_engine_changes() handles deleted files
# ---------------------------------------------------------------------------

class TestCommitDeletedFiles:
    def test_deleted_file_removed_from_run_engine(self, tmp_path):
        """File deleted from workspace engine/ should be removed from run engine."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "obsolete.py").write_text("# old")

        workspace = tmp_path / "workspace"
        engine_ws = workspace / "engine"
        engine_ws.mkdir(parents=True)
        # Don't copy obsolete.py to workspace — simulates deletion

        updated = commit_engine_changes(workspace, run_engine)
        assert any("obsolete.py" in u for u in updated)
        assert not (run_engine / "obsolete.py").exists()


# ---------------------------------------------------------------------------
# 8. save_engine_final() copies final state to output
# ---------------------------------------------------------------------------

class TestSaveEngineFinal:
    def test_saves_to_engine_final_dir(self, tmp_path):
        """save_engine_final should copy run_engine to engine_final/."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("final version")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = save_engine_final(run_engine, output_dir)
        assert result == output_dir / "engine_final"
        assert result.is_dir()
        assert (result / "card.py").read_text() == "final version"

    def test_overwrites_existing_engine_final(self, tmp_path):
        """Calling save_engine_final twice should replace the previous."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("v1")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        save_engine_final(run_engine, output_dir)
        # Modify and save again
        (run_engine / "card.py").write_text("v2")
        result = save_engine_final(run_engine, output_dir)
        assert (result / "card.py").read_text() == "v2"

    def test_preserves_subdirectory_structure(self, tmp_path):
        """Subdirectories in run engine should be preserved in final."""
        run_engine = tmp_path / "run_engine"
        (run_engine / "sub").mkdir(parents=True)
        (run_engine / "sub" / "mod.py").write_text("# sub mod")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = save_engine_final(run_engine, output_dir)
        assert (result / "sub" / "mod.py").read_text() == "# sub mod"


# ---------------------------------------------------------------------------
# 9. Multiple cards in sequence: card 2 sees changes from card 1
# ---------------------------------------------------------------------------

class TestSequentialCards:
    def test_card2_sees_card1_engine_changes(self, tmp_path):
        """After card 1 modifies engine and commits, card 2's workspace should have those changes."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original")

        # Card 1 workspace
        ws1 = tmp_path / "ws1"
        engine1 = ws1 / "engine"
        engine1.mkdir(parents=True)
        (engine1 / "card.py").write_text("modified by card 1")
        (engine1 / "new_helper.py").write_text("# added by card 1")

        # Commit card 1 changes
        commit_engine_changes(ws1, run_engine)

        # Verify run engine has card 1's changes
        assert (run_engine / "card.py").read_text() == "modified by card 1"
        assert (run_engine / "new_helper.py").read_text() == "# added by card 1"

        # Card 2 workspace copies from run_engine
        ws2 = tmp_path / "ws2"
        engine2 = ws2 / "engine"
        shutil.copytree(run_engine, engine2)

        # Card 2 should see card 1's changes
        assert (engine2 / "card.py").read_text() == "modified by card 1"
        assert (engine2 / "new_helper.py").read_text() == "# added by card 1"


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_engine_dir(self, tmp_path):
        """commit_engine_changes with empty engine dirs should return empty list."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        workspace = tmp_path / "workspace"
        engine_ws = workspace / "engine"
        engine_ws.mkdir(parents=True)

        updated = commit_engine_changes(workspace, run_engine)
        assert updated == []

    def test_save_engine_final_empty_dir(self, tmp_path):
        """save_engine_final with empty run engine should still create engine_final/."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = save_engine_final(run_engine, output_dir)
        assert result.is_dir()
        assert list(result.iterdir()) == []

    def test_init_run_engine_creates_output_dir_parent(self, tmp_path):
        """init_run_engine should work when output_dir already exists."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        result = init_run_engine(output_dir)
        assert result.is_dir()

    def test_binary_files_committed(self, tmp_path):
        """Binary files should be handled correctly by commit_engine_changes."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "data.bin").write_bytes(b"\x00\x01\x02")

        workspace = tmp_path / "workspace"
        engine_ws = workspace / "engine"
        engine_ws.mkdir(parents=True)
        (engine_ws / "data.bin").write_bytes(b"\x03\x04\x05")

        updated = commit_engine_changes(workspace, run_engine)
        assert "data.bin" in updated
        assert (run_engine / "data.bin").read_bytes() == b"\x03\x04\x05"
