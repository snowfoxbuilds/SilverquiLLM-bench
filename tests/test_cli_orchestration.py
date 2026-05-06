"""Tests for TODO item 5: Wire `benchmark run` orchestration loop.

Tests verify:
- The orchestration loop creates a results directory with expected structure.
- Mock `_run_opencode` to produce a stub blind_impl.py; verify result.json exists.
- Verify blind_impl.py source is saved in the card results.
- Verify per-card progress output is printed.
- If blind result has non-ok status (e.g., timeout), test_informed is skipped.
- The `_session_results_to_dicts` helper converts results correctly.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
from click.testing import CliRunner

from benchmark.agent_session import AgentSession, BlindResult, TestInformedResult
from benchmark.cli import main
from benchmark.config import BenchmarkConfig
from benchmark.run_utils import _session_results_to_dicts


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_MINIMAL_CONFIG = {
    "name": "test-orchestration",
    "set_code": "SOS",
    "model_name": "test-model",
    "model_provider": "test-provider",
}


def _write_config(tmp_path: Path, overrides: dict | None = None) -> Path:
    """Write a minimal config YAML and return the path."""
    cfg = {**_MINIMAL_CONFIG, **(overrides or {})}
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(cfg))
    return config_file


def _fake_run_opencode_creates_blind_impl(prompt: str, workspace: Path) -> str:
    """Fake _run_opencode that writes blind_impl.py into the workspace."""
    impl_code = "# Stub blind implementation\nclass EagerGlyphmage:\n    pass\n"
    (workspace / "blind_impl.py").write_text(impl_code)
    return "Done"


# ---------------------------------------------------------------------------
# Tests for _session_results_to_dicts helper
# ---------------------------------------------------------------------------


class TestSessionResultsToDicts:
    """Unit tests for _session_results_to_dicts."""

    def test_blind_only_returns_blind_dict_with_impl_source(self, tmp_path: Path) -> None:
        """When tested is None, test_dict should be empty."""
        impl_file = tmp_path / "blind_impl.py"
        impl_file.write_text("class Foo:\n    pass\n")

        blind = BlindResult(
            impl_path=impl_file,
            tokens=100,
            runtime_seconds=5.0,
            peak_context=200,
            status="ok",
        )
        spec = {"name": "Test Card", "tier": "simple", "collector_number": "11"}
        config = BenchmarkConfig(
            name="test",
            set_code="SOS",
            model_name="test-model",
            model_provider="test-provider",
        )

        blind_dict, test_dict = _session_results_to_dicts(blind, None, spec, config)

        assert blind_dict["status"] == "ok"
        assert blind_dict["tokens"] == 100
        assert blind_dict["runtime_seconds"] == 5.0
        assert blind_dict["peak_context"] == 200
        assert blind_dict["impl_source"] == "class Foo:\n    pass\n"
        assert blind_dict["complexity_tier"] == "simple"
        assert test_dict == {}

    def test_with_tested_result_returns_both_dicts(self, tmp_path: Path) -> None:
        """When tested is provided, test_dict has impl_source and tests_source."""
        blind_file = tmp_path / "blind_impl.py"
        blind_file.write_text("class Blind:\n    pass\n")
        tested_file = tmp_path / "tested_impl.py"
        tested_file.write_text("class Tested:\n    pass\n")
        tests_file = tmp_path / "tests.py"
        tests_file.write_text("def test_it(): pass\n")

        blind = BlindResult(
            impl_path=blind_file, tokens=50, runtime_seconds=2.0,
            peak_context=100, status="ok",
        )
        tested = TestInformedResult(
            impl_path=tested_file, tests_path=tests_file,
            iterations=3, tokens=200, runtime_seconds=10.0,
            peak_context=400, rules_lookups=2, status="ok",
        )
        spec = {"name": "Card", "tier": "complex"}
        config = BenchmarkConfig(
            name="test", set_code="SOS",
            model_name="m", model_provider="p",
        )

        blind_dict, test_dict = _session_results_to_dicts(blind, tested, spec, config)

        assert blind_dict["impl_source"] == "class Blind:\n    pass\n"
        assert test_dict["status"] == "ok"
        assert test_dict["impl_source"] == "class Tested:\n    pass\n"
        assert test_dict["tests_source"] == "def test_it(): pass\n"
        assert test_dict["iterations"] == 3
        assert test_dict["rules_lookups"] == 2

    def test_none_impl_path_returns_empty_source(self) -> None:
        """When impl_path is None, impl_source is empty string."""
        blind = BlindResult(
            impl_path=None, tokens=0, runtime_seconds=1.0,
            peak_context=0, status="timeout",
        )
        spec = {"name": "Card"}
        config = BenchmarkConfig(
            name="test", set_code="SOS",
            model_name="m", model_provider="p",
        )

        blind_dict, _ = _session_results_to_dicts(blind, None, spec, config)

        assert blind_dict["impl_source"] == ""
        assert blind_dict["status"] == "timeout"


# ---------------------------------------------------------------------------
# Integration tests for the orchestration loop via CLI
# ---------------------------------------------------------------------------


class TestOrchestrationLoop:
    """Test the `benchmark run` orchestration loop end-to-end with mocks."""

    def _patch_session_for_stub(self):
        """Return a context manager that patches AgentSession methods to produce stub results."""
        def fake_setup_workspace(self_session):
            workspace = Path(tempfile.mkdtemp(prefix="test_bench_"))
            self_session._workspace = workspace
            return workspace

        def fake_run_blind(self_session, workspace):
            impl_code = "# Stub blind implementation\nclass EagerGlyphmage:\n    pass\n"
            impl_path = workspace / "blind_impl.py"
            impl_path.write_text(impl_code)
            return BlindResult(
                impl_path=impl_path,
                tokens=42,
                runtime_seconds=1.5,
                peak_context=100,
                status="ok",
            )

        def fake_run_test_informed(self_session, workspace, blind_impl):
            tested_code = "# Tested impl\nclass EagerGlyphmage:\n    def ability(self): pass\n"
            impl_path = workspace / "tested_impl.py"
            impl_path.write_text(tested_code)
            tests_path = workspace / "tests.py"
            tests_path.write_text("def test_glyphmage(): pass\n")
            return TestInformedResult(
                impl_path=impl_path,
                tests_path=tests_path,
                iterations=2,
                tokens=80,
                runtime_seconds=3.0,
                peak_context=200,
                rules_lookups=1,
                status="ok",
            )

        def fake_cleanup(self_session):
            pass  # Don't actually clean up temp dirs during test

        return [
            patch.object(AgentSession, "setup_workspace", fake_setup_workspace),
            patch.object(AgentSession, "run_blind_implementation", fake_run_blind),
            patch.object(AgentSession, "run_test_informed", fake_run_test_informed),
            patch.object(AgentSession, "cleanup", fake_cleanup),
        ]

    def test_orchestration_creates_result_json(self, tmp_path: Path) -> None:
        """Running with --cards 11 creates result.json for card 11."""
        config_file = _write_config(tmp_path, {"output_dir": str(tmp_path / "results")})
        runner = CliRunner()

        patches = self._patch_session_for_stub()
        with patches[0], patches[1], patches[2], patches[3]:
            result = runner.invoke(main, ["run", "--config", str(config_file), "--cards", "11"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        # Find the run directory
        results_dir = tmp_path / "results"
        assert results_dir.exists(), "Results directory not created"
        run_dirs = list(results_dir.iterdir())
        assert len(run_dirs) == 1, f"Expected 1 run dir, got {run_dirs}"
        run_dir = run_dirs[0]

        result_json = run_dir / "cards" / "11" / "result.json"
        assert result_json.exists(), f"result.json not found; contents: {list((run_dir / 'cards').rglob('*'))}"

        data = json.loads(result_json.read_text())
        assert "blind" in data or "status" in data  # Has result structure

    def test_orchestration_saves_blind_impl(self, tmp_path: Path) -> None:
        """Running with --cards 11 saves blind_impl.py in the card results."""
        config_file = _write_config(tmp_path, {"output_dir": str(tmp_path / "results")})
        runner = CliRunner()

        patches = self._patch_session_for_stub()
        with patches[0], patches[1], patches[2], patches[3]:
            result = runner.invoke(main, ["run", "--config", str(config_file), "--cards", "11"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        results_dir = tmp_path / "results"
        run_dirs = list(results_dir.iterdir())
        run_dir = run_dirs[0]

        blind_impl = run_dir / "cards" / "11" / "blind_impl.py"
        assert blind_impl.exists(), "blind_impl.py not saved in results"
        content = blind_impl.read_text()
        assert "EagerGlyphmage" in content

    def test_orchestration_prints_progress(self, tmp_path: Path) -> None:
        """Running the loop prints per-card progress like [1/1] CardName: blind=ok."""
        config_file = _write_config(tmp_path, {"output_dir": str(tmp_path / "results")})
        runner = CliRunner()

        patches = self._patch_session_for_stub()
        with patches[0], patches[1], patches[2], patches[3]:
            result = runner.invoke(main, ["run", "--config", str(config_file), "--cards", "11"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Should contain progress output with blind status
        assert "blind=" in result.output
        assert "1/" in result.output

    def test_test_informed_skipped_when_blind_fails(self, tmp_path: Path) -> None:
        """If blind result has non-ok status (timeout), test_informed is skipped."""
        config_file = _write_config(tmp_path, {"output_dir": str(tmp_path / "results")})

        def fake_setup_workspace(self_session):
            workspace = Path(tempfile.mkdtemp(prefix="test_bench_"))
            self_session._workspace = workspace
            return workspace

        def fake_run_blind_timeout(self_session, workspace):
            return BlindResult(
                impl_path=None,
                tokens=0,
                runtime_seconds=30.0,
                peak_context=0,
                status="timeout",
            )

        run_test_informed_mock = MagicMock()

        def fake_cleanup(self_session):
            pass

        runner = CliRunner()
        with (
            patch.object(AgentSession, "setup_workspace", fake_setup_workspace),
            patch.object(AgentSession, "run_blind_implementation", fake_run_blind_timeout),
            patch.object(AgentSession, "run_test_informed", run_test_informed_mock),
            patch.object(AgentSession, "cleanup", fake_cleanup),
        ):
            result = runner.invoke(main, ["run", "--config", str(config_file), "--cards", "11"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # test_informed should NOT have been called
        run_test_informed_mock.assert_not_called()
        # Progress should show "skipped" for tested
        assert "skipped" in result.output

    def test_orchestration_creates_run_directory_with_config(self, tmp_path: Path) -> None:
        """The orchestration loop creates a run directory with config.yaml."""
        config_file = _write_config(tmp_path, {"output_dir": str(tmp_path / "results")})
        runner = CliRunner()

        patches = self._patch_session_for_stub()
        with patches[0], patches[1], patches[2], patches[3]:
            result = runner.invoke(main, ["run", "--config", str(config_file), "--cards", "11"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        results_dir = tmp_path / "results"
        run_dirs = list(results_dir.iterdir())
        assert len(run_dirs) == 1
        run_dir = run_dirs[0]

        # Should have config.yaml in the run directory
        assert (run_dir / "config.yaml").exists()
        # Should have cards/ subdirectory
        assert (run_dir / "cards").is_dir()
