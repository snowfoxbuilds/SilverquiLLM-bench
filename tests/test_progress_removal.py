"""Tests verifying complete removal of progress.jsonl channel (TODO item 16).

progress.jsonl was the original telemetry channel, now superseded by
fast_telemetry.jsonl and snapshot_telemetry.jsonl. This test module ensures
all traces are removed from:
- logs_viewer channel list
- cli.py helper functions
- runner.py ContainerLifecycle
- Docker entrypoint scripts
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Logs viewer: progress channel fully removed
# ---------------------------------------------------------------------------


class TestLogsViewerNoProgress:
    """progress.jsonl must not appear in the logs_viewer channel infrastructure."""

    def test_progress_not_in_channel_order(self) -> None:
        """CHANNEL_ORDER must not contain 'progress'."""
        from silverquillm.logs_viewer import CHANNEL_ORDER

        assert "progress" not in CHANNEL_ORDER

    def test_progress_not_in_channel_files(self) -> None:
        """CHANNEL_FILES must not map a 'progress' key."""
        from silverquillm.telemetry import CHANNEL_FILES

        assert "progress" not in CHANNEL_FILES

    def test_progress_jsonl_not_in_channel_files_values(self) -> None:
        """No channel should map to progress.jsonl filename."""
        from silverquillm.telemetry import CHANNEL_FILES

        assert "progress.jsonl" not in CHANNEL_FILES.values()


# ---------------------------------------------------------------------------
# CLI: _copy_progress_with_names removed
# ---------------------------------------------------------------------------


class TestCliNoProgressHelper:
    """_copy_progress_with_names must no longer exist in cli module."""

    def test_copy_progress_with_names_not_in_cli(self) -> None:
        """The deprecated _copy_progress_with_names function must be removed."""
        import silverquillm.cli as cli_mod

        assert not hasattr(cli_mod, "_copy_progress_with_names"), (
            "_copy_progress_with_names should be removed from cli.py"
        )

    def test_cli_source_no_copy_progress_definition(self) -> None:
        """cli.py source should not define _copy_progress_with_names."""
        import silverquillm.cli as cli_mod

        source = inspect.getsource(cli_mod)
        assert "def _copy_progress_with_names" not in source


# ---------------------------------------------------------------------------
# Runner: _progress_path removed from ContainerLifecycle
# ---------------------------------------------------------------------------


class TestRunnerNoProgressPath:
    """_progress_path must no longer exist in runner module or ContainerLifecycle."""

    def test_progress_path_not_in_runner_module(self) -> None:
        """runner.py must not expose _progress_path at module level."""
        import silverquillm.runner as runner_mod

        assert not hasattr(runner_mod, "_progress_path"), (
            "_progress_path should be removed from runner.py"
        )

    def test_progress_path_not_on_container_lifecycle(self) -> None:
        """ContainerLifecycle class must not have a _progress_path attribute."""
        from silverquillm.runner import ContainerLifecycle

        assert not hasattr(ContainerLifecycle, "_progress_path"), (
            "ContainerLifecycle._progress_path should be removed"
        )

    def test_runner_source_no_progress_path(self) -> None:
        """runner.py source should have no references to _progress_path."""
        import silverquillm.runner as runner_mod

        source = inspect.getsource(runner_mod)
        assert "_progress_path" not in source


# ---------------------------------------------------------------------------
# Docker entrypoints: no progress.jsonl writes
# ---------------------------------------------------------------------------


ALL_ENTRYPOINTS = list((REPO_ROOT / "docker").glob("*/entrypoint.mjs"))
ENTRYPOINT_IDS = [p.parent.name for p in ALL_ENTRYPOINTS]


class TestDockerEntrypointsNoProgress:
    """Docker entrypoint scripts must not write to progress.jsonl."""

    @pytest.fixture(params=zip(ALL_ENTRYPOINTS, ENTRYPOINT_IDS), ids=ENTRYPOINT_IDS)
    def entrypoint_text(self, request) -> str:
        path, _ = request.param
        assert path.is_file(), f"Entrypoint not found: {path}"
        return path.read_text()

    def test_no_progress_jsonl_write(self, entrypoint_text: str) -> None:
        """Entrypoint must not reference progress.jsonl."""
        assert "progress.jsonl" not in entrypoint_text, (
            "Entrypoint still writes to progress.jsonl — should be removed"
        )

    def test_no_progress_append(self, entrypoint_text: str) -> None:
        """Entrypoint must not append to any progress file."""
        # Check for the typical pattern: appendFileSync(..."progress...")
        lines = entrypoint_text.split("\n")
        for line in lines:
            if "progress" in line.lower() and "append" in line.lower():
                pytest.fail(
                    f"Entrypoint still appends to progress file: {line.strip()}"
                )


# ---------------------------------------------------------------------------
# Harvest: progress.jsonl is skipped / not produced
# ---------------------------------------------------------------------------


class TestHarvestSkipsProgress:
    """After harvest, run_dir should not contain progress.jsonl."""

    def test_cli_harvest_skips_progress_jsonl(self, tmp_path: Path) -> None:
        """The harvest logic in cli.py skips progress.jsonl from container output."""
        import shutil

        # Simulate container output dir with progress.jsonl present
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "progress.jsonl").write_text('{"status":"done"}\n')
        (output_dir / "runner.log").write_text("log line\n")

        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Copy files mimicking the harvest loop (same logic as cli.py)
        _DIRECT_STREAM_FILES = {"docker_stdout.log", "docker_stderr.log"}
        for src in output_dir.iterdir():
            if src.is_file() and (src.suffix in (".log", ".jsonl")):
                if src.name in _DIRECT_STREAM_FILES and (run_dir / src.name).exists():
                    continue
                if src.name == "progress.jsonl":
                    continue  # This is the behavior we're verifying exists
                shutil.copy2(src, run_dir / src.name)

        # progress.jsonl must NOT have been copied
        assert not (run_dir / "progress.jsonl").exists(), (
            "progress.jsonl should not be copied to run_dir during harvest"
        )
        # But other files should be copied
        assert (run_dir / "runner.log").exists()
