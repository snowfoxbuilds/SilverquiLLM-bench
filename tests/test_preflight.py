"""Tests for silverquillm.preflight — pre-flight validation at run start."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.preflight import PreflightError, preflight_check


def _make_config(
    adapter: str = "opencode",
    timeout_per_card: int = 300,
    mode: str = "impl_test",
    card_specs_dir: str = "",
) -> BenchmarkConfig:
    """Build a minimal BenchmarkConfig for testing."""
    return BenchmarkConfig(
        name="test-run",
        set_code="TST",
        model_name="test-model",
        model_provider="test-provider",
        agent=AgentConfig(adapter=adapter, timeout_per_card=timeout_per_card),
        mode=mode,
        card_specs_dir=card_specs_dir,
    )


# ---------------------------------------------------------------------------
# card_specs_dir checks
# ---------------------------------------------------------------------------


class TestCardSpecsDir:
    """Tests for card_specs_dir validation."""

    def test_missing_card_specs_dir(self, tmp_path: Path):
        """Missing card_specs_dir → preflight fails with clear message."""
        config = _make_config(card_specs_dir=str(tmp_path / "nonexistent"))
        with pytest.raises(PreflightError, match="card_specs_dir does not exist"):
            preflight_check(config, tmp_path / "run")

    def test_empty_card_specs_dir(self, tmp_path: Path):
        """card_specs_dir with no spec files → preflight fails."""
        empty_dir = tmp_path / "specs"
        empty_dir.mkdir()
        config = _make_config(card_specs_dir=str(empty_dir))
        with pytest.raises(PreflightError, match="no card spec files"):
            preflight_check(config, tmp_path / "run")

    def test_card_specs_dir_is_file(self, tmp_path: Path):
        """card_specs_dir pointing to a file → preflight fails."""
        a_file = tmp_path / "not_a_dir.yaml"
        a_file.write_text("hello")
        config = _make_config(card_specs_dir=str(a_file))
        with pytest.raises(PreflightError, match="not a directory"):
            preflight_check(config, tmp_path / "run")

    def test_card_specs_dir_with_specs_passes(self, tmp_path: Path):
        """card_specs_dir containing YAML specs → check passes."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "card1.yaml").write_text("id: card1")
        config = _make_config(card_specs_dir=str(specs_dir))
        # Should not raise for this check (other checks may still fail)
        from silverquillm.preflight import _check_card_specs_dir

        errors = _check_card_specs_dir(config)
        assert errors == []

    def test_card_specs_dir_empty_string_skipped(self, tmp_path: Path):
        """Empty card_specs_dir string → check is skipped (no error)."""
        from silverquillm.preflight import _check_card_specs_dir

        config = _make_config(card_specs_dir="")
        errors = _check_card_specs_dir(config)
        assert errors == []


# ---------------------------------------------------------------------------
# Config validation checks
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Tests for config field validation (timeout, adapter, mode)."""

    def test_invalid_adapter_name(self, tmp_path: Path):
        """Unknown adapter name → preflight fails with available list."""
        config = _make_config(adapter="nonexistent_adapter_xyz")
        with pytest.raises(PreflightError, match="Unknown adapter.*nonexistent_adapter_xyz"):
            preflight_check(config, tmp_path / "run")

    def test_timeout_zero(self, tmp_path: Path):
        """timeout_per_card == 0 → preflight fails."""
        config = _make_config(timeout_per_card=0)
        with pytest.raises(PreflightError, match="timeout_per_card must be > 0"):
            preflight_check(config, tmp_path / "run")

    def test_timeout_negative(self, tmp_path: Path):
        """timeout_per_card < 0 → preflight fails."""
        config = _make_config(timeout_per_card=-10)
        with pytest.raises(PreflightError, match="timeout_per_card must be > 0"):
            preflight_check(config, tmp_path / "run")

    def test_invalid_mode(self, tmp_path: Path):
        """Invalid mode → preflight fails."""
        from silverquillm.preflight import _check_config

        # BenchmarkConfig validates mode in __init__, so build a valid config
        # then monkey-patch mode to bypass constructor validation
        config = _make_config(mode="impl_test")
        config.mode = "invalid_mode"
        errors = _check_config(config)
        assert any("Invalid mode" in e for e in errors)


# ---------------------------------------------------------------------------
# Workspace check
# ---------------------------------------------------------------------------


class TestWorkspace:
    """Tests for workspace directory creation."""

    def test_workspace_created(self, tmp_path: Path):
        """Run directory can be created."""
        from silverquillm.preflight import _check_workspace

        run_dir = tmp_path / "results" / "run_001"
        errors = _check_workspace(run_dir)
        assert errors == []
        assert run_dir.exists()

    def test_workspace_permission_error(self, tmp_path: Path):
        """Uncreatable run directory → error reported."""
        from silverquillm.preflight import _check_workspace

        # Use a path under /proc which cannot be created
        errors = _check_workspace(Path("/proc/nonexistent/run_dir"))
        assert len(errors) == 1
        assert "Cannot create run directory" in errors[0]


# ---------------------------------------------------------------------------
# Template imports check
# ---------------------------------------------------------------------------


class TestTemplateImports:
    """Tests for template.py import resolution."""

    def test_template_imports_succeed(self):
        """engine.game_state and engine.card should be importable."""
        from silverquillm.preflight import _check_template_imports

        errors = _check_template_imports()
        assert errors == []

    def test_template_import_failure_reported(self):
        """Failed template import → clear error message."""
        from silverquillm.preflight import _check_template_imports

        with patch("importlib.import_module", side_effect=ImportError("no module")):
            errors = _check_template_imports()
        assert len(errors) >= 1
        assert any("Template import failed" in e for e in errors)


# ---------------------------------------------------------------------------
# test_utils import check
# ---------------------------------------------------------------------------


class TestTestUtilsImport:
    """Tests for test_utils.py importability check."""

    def test_test_utils_exists(self):
        """test_utils.py should exist at tests/test_utils.py."""
        from silverquillm.preflight import _check_test_utils_import

        errors = _check_test_utils_import()
        assert errors == []

    def test_test_utils_missing_reported(self, tmp_path: Path):
        """Missing test_utils.py → clear error."""
        from silverquillm.preflight import _check_test_utils_import

        # Point __file__ to a fake location so repo_root resolves to tmp_path
        fake_file = str(tmp_path / "silverquillm" / "preflight.py")
        with patch("silverquillm.preflight.__file__", fake_file):
            errors = _check_test_utils_import()
        assert len(errors) == 1
        assert "test_utils.py not found" in errors[0]

    def test_test_utils_import_failure_reported(self, tmp_path: Path):
        """test_utils.py exists but 'from test_utils import create_game' fails → error."""
        from silverquillm.preflight import _check_test_utils_import

        # Create a test_utils.py that has a syntax error / no create_game
        fake_root = tmp_path / "fakerepo"
        (fake_root / "silverquillm").mkdir(parents=True)
        tests_dir = fake_root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_utils.py").write_text("# no create_game here\nx = 1\n")

        fake_file = str(fake_root / "silverquillm" / "preflight.py")
        with patch("silverquillm.preflight.__file__", fake_file):
            errors = _check_test_utils_import()
        assert len(errors) == 1
        assert "from test_utils import create_game" in errors[0]

    def test_test_utils_subprocess_import_success(self):
        """Actual import check verifies create_game is callable, not just file existence."""
        from silverquillm.preflight import _check_test_utils_import

        # The real test_utils.py in the repo should have create_game
        # and the subprocess import should succeed
        errors = _check_test_utils_import()
        assert errors == []


# ---------------------------------------------------------------------------
# Engine test suite check
# ---------------------------------------------------------------------------


class TestEngineTestSuite:
    """Tests for engine test suite execution via subprocess."""

    def test_engine_tests_called_via_subprocess(self):
        """_check_engine_tests runs pytest on tests/engine/ via subprocess."""
        from silverquillm.preflight import _check_engine_tests

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "all passed"
        mock_result.stderr = ""

        with patch("silverquillm.preflight.subprocess.run", return_value=mock_result) as mock_run:
            errors = _check_engine_tests()

        assert errors == []
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # Verify pytest is invoked with -x -q flags
        cmd = call_args[0][0]
        assert "-m" in cmd and "pytest" in cmd
        assert "-x" in cmd
        assert "-q" in cmd

    def test_engine_tests_failure_propagates(self):
        """Failed engine tests → error reported with exit code and summary."""
        from silverquillm.preflight import _check_engine_tests

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "FAILED tests/engine/test_foo.py::test_bar\n1 failed"
        mock_result.stderr = ""

        with patch("silverquillm.preflight.subprocess.run", return_value=mock_result):
            errors = _check_engine_tests()

        assert len(errors) == 1
        assert "Engine test suite failed" in errors[0]
        assert "exit code 1" in errors[0]

    def test_engine_tests_timeout_reported(self):
        """Engine test suite timeout → error reported."""
        from silverquillm.preflight import _check_engine_tests

        with patch(
            "silverquillm.preflight.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=120),
        ):
            errors = _check_engine_tests()

        assert len(errors) == 1
        assert "timed out" in errors[0].lower()

    def test_engine_tests_missing_dir(self, tmp_path: Path):
        """Missing tests/engine/ directory → error reported."""
        from silverquillm.preflight import _check_engine_tests

        # Point _REPO_ROOT to a temp dir without tests/engine/
        with patch("silverquillm.preflight._REPO_ROOT", tmp_path):
            errors = _check_engine_tests()

        assert len(errors) == 1
        assert "Engine test directory not found" in errors[0]


# ---------------------------------------------------------------------------
# .workspace/ directory check
# ---------------------------------------------------------------------------


class TestWorkspaceDir:
    """Tests for .workspace/ directory creation and cleanup."""

    def test_workspace_dir_created(self, tmp_path: Path):
        """_check_workspace_dir can create .workspace/ directory."""
        from silverquillm.preflight import _check_workspace_dir

        with patch("silverquillm.preflight._REPO_ROOT", tmp_path):
            errors = _check_workspace_dir()

        assert errors == []
        assert (tmp_path / ".workspace").is_dir()

    def test_workspace_dir_stale_contents_writable(self, tmp_path: Path):
        """Pre-existing .workspace/ with normal files → check passes."""
        from silverquillm.preflight import _check_workspace_dir

        ws = tmp_path / ".workspace"
        ws.mkdir()
        (ws / "stale_file.txt").write_text("stale")

        with patch("silverquillm.preflight._REPO_ROOT", tmp_path):
            errors = _check_workspace_dir()

        assert errors == []

    def test_workspace_dir_uncreatable_reports_error(self):
        """Uncreatable .workspace/ → error reported."""
        from silverquillm.preflight import _check_workspace_dir

        # Use a path that can't have directories created under it
        with patch("silverquillm.preflight._REPO_ROOT", Path("/proc/nonexistent")):
            errors = _check_workspace_dir()

        assert len(errors) == 1
        assert ".workspace/" in errors[0]


# ---------------------------------------------------------------------------
# Happy path — all checks pass
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Tests for successful preflight validation."""

    def test_all_checks_pass(self, tmp_path: Path):
        """Valid config with existing card specs → preflight succeeds (no exception)."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "card1.yaml").write_text("id: card1")

        config = _make_config(card_specs_dir=str(specs_dir))
        # Mock workspace isolation so the real adapter isn't needed
        with patch("silverquillm.preflight._check_workspace_isolation", return_value=[]):
            preflight_check(config, tmp_path / "run")


# ---------------------------------------------------------------------------
# Error aggregation
# ---------------------------------------------------------------------------


class TestErrorAggregation:
    """Tests for error message quality."""

    def test_multiple_errors_aggregated(self, tmp_path: Path):
        """Multiple failures → all reported in single PreflightError."""
        config = _make_config(
            adapter="nonexistent_xyz",
            timeout_per_card=-1,
            card_specs_dir=str(tmp_path / "missing"),
        )
        with pytest.raises(PreflightError) as exc_info:
            preflight_check(config, tmp_path / "run")

        msg = str(exc_info.value)
        assert "timeout_per_card" in msg
        assert "nonexistent_xyz" in msg
        assert "card_specs_dir" in msg

    def test_error_message_is_actionable(self, tmp_path: Path):
        """Error message includes 'Pre-flight checks failed' header."""
        config = _make_config(adapter="bogus_adapter")
        with pytest.raises(PreflightError, match="Pre-flight checks failed"):
            preflight_check(config, tmp_path / "run")


# ---------------------------------------------------------------------------
# Workspace isolation check
# ---------------------------------------------------------------------------


class TestWorkspaceIsolation:
    """Tests for _check_workspace_isolation() canary-file check."""

    def test_canary_file_created_with_uuid_content(self, tmp_path: Path):
        """_check_workspace_isolation creates a canary file containing a UUID."""
        from silverquillm.preflight import _check_workspace_isolation

        config = _make_config()
        canary_path = tmp_path / ".canary_preflight"
        fake_uuid = "12345678-1234-5678-1234-567812345678"

        mock_adapter = MagicMock()
        mock_adapter.run.return_value = "some unrelated output"

        with (
            patch("silverquillm.preflight._REPO_ROOT", tmp_path),
            patch("silverquillm.adapters.base.get_adapter", return_value=mock_adapter),
            patch("silverquillm.preflight.uuid.uuid4", return_value=fake_uuid),
        ):
            # The canary file is created and deleted within the call,
            # but we can verify the adapter prompt includes the canary path
            _check_workspace_isolation(config)

        # Verify adapter.run was called with a prompt referencing the canary path
        mock_adapter.run.assert_called_once()
        prompt_arg = mock_adapter.run.call_args[0][0]
        assert str(canary_path) in prompt_arg

    def test_canary_file_cleaned_up_after_success(self, tmp_path: Path):
        """Canary file is deleted after a successful check (adapter returns unrelated text)."""
        from silverquillm.preflight import _check_workspace_isolation

        config = _make_config()
        canary_path = tmp_path / ".canary_preflight"

        mock_adapter = MagicMock()
        mock_adapter.run.return_value = "nothing relevant here"

        with (
            patch("silverquillm.preflight._REPO_ROOT", tmp_path),
            patch("silverquillm.adapters.base.get_adapter", return_value=mock_adapter),
        ):
            errors = _check_workspace_isolation(config)

        assert errors == []
        assert not canary_path.exists(), "Canary file should be cleaned up after check"

    def test_canary_file_cleaned_up_on_adapter_exception(self, tmp_path: Path):
        """Canary file is deleted even when the adapter raises an exception."""
        from silverquillm.preflight import _check_workspace_isolation

        config = _make_config()
        canary_path = tmp_path / ".canary_preflight"

        mock_adapter = MagicMock()
        mock_adapter.run.side_effect = RuntimeError("adapter exploded")

        with (
            patch("silverquillm.preflight._REPO_ROOT", tmp_path),
            patch("silverquillm.adapters.base.get_adapter", return_value=mock_adapter),
        ):
            errors = _check_workspace_isolation(config)

        assert not canary_path.exists(), "Canary file must be cleaned up even on error"

    def test_adapter_returning_uuid_reports_isolation_breach(self, tmp_path: Path):
        """When adapter output contains the canary UUID, an isolation error is reported."""
        from silverquillm.preflight import _check_workspace_isolation

        config = _make_config()
        fake_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        mock_adapter = MagicMock()
        # The adapter returns the exact canary UUID — simulating workspace escape
        mock_adapter.run.return_value = f"Here is the content: {fake_uuid}"

        with (
            patch("silverquillm.preflight._REPO_ROOT", tmp_path),
            patch("silverquillm.adapters.base.get_adapter", return_value=mock_adapter),
            patch("silverquillm.preflight.uuid.uuid4", return_value=fake_uuid),
        ):
            errors = _check_workspace_isolation(config)

        assert len(errors) == 1
        assert "Workspace isolation FAILED" in errors[0]

    def test_adapter_returning_unrelated_text_passes(self, tmp_path: Path):
        """When adapter output does NOT contain the canary UUID, no error is reported."""
        from silverquillm.preflight import _check_workspace_isolation

        config = _make_config()

        mock_adapter = MagicMock()
        mock_adapter.run.return_value = "I cannot read files outside my workspace."

        with (
            patch("silverquillm.preflight._REPO_ROOT", tmp_path),
            patch("silverquillm.adapters.base.get_adapter", return_value=mock_adapter),
        ):
            errors = _check_workspace_isolation(config)

        assert errors == []

    def test_adapter_exception_handled_gracefully(self, tmp_path: Path):
        """Adapter raising exception → surfaces as a preflight error (not silent skip)."""
        from silverquillm.preflight import _check_workspace_isolation

        config = _make_config()

        mock_adapter = MagicMock()
        mock_adapter.run.side_effect = ConnectionError("network down")

        with (
            patch("silverquillm.preflight._REPO_ROOT", tmp_path),
            patch("silverquillm.adapters.base.get_adapter", return_value=mock_adapter),
        ):
            errors = _check_workspace_isolation(config)

        # Adapter failure should be reported as a preflight error
        assert len(errors) == 1
        assert "adapter error" in errors[0]
        assert "network down" in errors[0]

    def test_adapter_returning_none_passes(self, tmp_path: Path):
        """Adapter returning None output → no crash, no isolation error."""
        from silverquillm.preflight import _check_workspace_isolation

        config = _make_config()

        mock_adapter = MagicMock()
        mock_adapter.run.return_value = None

        with (
            patch("silverquillm.preflight._REPO_ROOT", tmp_path),
            patch("silverquillm.adapters.base.get_adapter", return_value=mock_adapter),
        ):
            errors = _check_workspace_isolation(config)

        assert errors == []


# ---------------------------------------------------------------------------
# preflight_check isolation-check gating
# ---------------------------------------------------------------------------


class TestIsolationCheckGating:
    """Tests that preflight_check respects skip_isolation_check flag."""

    def test_preflight_skips_isolation_when_flag_true(self, tmp_path: Path):
        """preflight_check with skip_isolation_check=True does NOT call _check_workspace_isolation."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "card1.yaml").write_text("id: card1")
        config = _make_config(card_specs_dir=str(specs_dir))

        with patch(
            "silverquillm.preflight._check_workspace_isolation"
        ) as mock_iso:
            preflight_check(config, tmp_path / "run", skip_isolation_check=True)

        mock_iso.assert_not_called()

    def test_preflight_runs_isolation_when_flag_false(self, tmp_path: Path):
        """preflight_check with skip_isolation_check=False calls _check_workspace_isolation."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "card1.yaml").write_text("id: card1")
        config = _make_config(card_specs_dir=str(specs_dir))

        with patch(
            "silverquillm.preflight._check_workspace_isolation", return_value=[]
        ) as mock_iso:
            preflight_check(config, tmp_path / "run", skip_isolation_check=False)

        mock_iso.assert_called_once_with(config)

    def test_preflight_runs_isolation_by_default(self, tmp_path: Path):
        """preflight_check without skip_isolation_check kwarg calls _check_workspace_isolation."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "card1.yaml").write_text("id: card1")
        config = _make_config(card_specs_dir=str(specs_dir))

        with patch(
            "silverquillm.preflight._check_workspace_isolation", return_value=[]
        ) as mock_iso:
            preflight_check(config, tmp_path / "run")

        mock_iso.assert_called_once()


# ---------------------------------------------------------------------------
# CLI --skip-isolation-check flag
# ---------------------------------------------------------------------------


class TestCLISkipIsolationFlag:
    """Tests for --skip-isolation-check CLI flag."""

    def test_skip_isolation_check_flag_accepted(self):
        """CLI accepts --skip-isolation-check without error."""
        from click.testing import CliRunner
        from silverquillm.cli import run

        runner = CliRunner()
        # Invoke with --help to verify the flag is registered (no real run needed)
        result = runner.invoke(run, ["--help"])
        assert result.exit_code == 0
        assert "--skip-isolation-check" in result.output
