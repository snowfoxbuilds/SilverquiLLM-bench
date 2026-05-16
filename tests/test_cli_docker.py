"""Tests for silverquillm.cli — run and smoke Docker commands."""

from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from silverquillm.cli import main, _make_run_name, _api_key_env_args, _harvest_results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Test: main() is a Click group with run and smoke commands
# ---------------------------------------------------------------------------


class TestCLIGroup:
    """Verify that main is a Click group with expected subcommands."""

    def test_main_is_click_group(self):
        """main() should be a Click group (callable)."""
        assert hasattr(main, "commands") or hasattr(main, "list_commands")

    def test_has_run_command(self, runner):
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "image" in result.output.lower()

    def test_has_smoke_command(self, runner):
        result = runner.invoke(main, ["smoke", "--help"])
        assert result.exit_code == 0
        assert "image" in result.output.lower()

    def test_help_text(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "smoke" in result.output


# ---------------------------------------------------------------------------
# Test: --cards-dir and --engine-dir CLI flags removed
# ---------------------------------------------------------------------------


class TestRemovedCLIFlags:
    """The --cards-dir and --engine-dir CLI flags must not exist."""

    def test_run_help_does_not_mention_cards_dir(self, runner):
        result = runner.invoke(main, ["run", "--help"])
        assert "--cards-dir" not in result.output

    def test_run_help_does_not_mention_engine_dir(self, runner):
        result = runner.invoke(main, ["run", "--help"])
        assert "--engine-dir" not in result.output

    def test_run_rejects_cards_dir_flag(self, runner):
        """Passing --cards-dir should cause an error (no such option)."""
        result = runner.invoke(main, ["run", "--image", "x", "--cards-dir", "/tmp"])
        assert result.exit_code != 0
        assert "no such option" in result.output.lower() or "error" in result.output.lower()

    def test_run_rejects_engine_dir_flag(self, runner):
        """Passing --engine-dir should cause an error (no such option)."""
        result = runner.invoke(main, ["run", "--image", "x", "--engine-dir", "/tmp"])
        assert result.exit_code != 0
        assert "no such option" in result.output.lower() or "error" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Run name format
# ---------------------------------------------------------------------------


class TestRunName:
    """Run names should match {image_short_name}_{ISO-timestamp} pattern."""

    def test_simple_image_name(self):
        name = _make_run_name("opencode-tested")
        assert name.startswith("opencode-tested_")
        # Check ISO timestamp portion: YYYY-MM-DDTHH-MM
        ts_part = name.split("_", 1)[1]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}", ts_part)

    def test_image_with_registry_and_tag(self):
        name = _make_run_name("ghcr.io/user/my-image:latest")
        assert name.startswith("my-image_")

    def test_image_with_tag_only(self):
        name = _make_run_name("opencode-blind:v2")
        assert name.startswith("opencode-blind_")


# ---------------------------------------------------------------------------
# Test: API key passthrough
# ---------------------------------------------------------------------------


class TestAPIKeyPassthrough:
    """API key env vars should appear in docker command args."""

    def test_passes_set_api_keys(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key456")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        args = _api_key_env_args()
        assert "-e" in args
        assert "OPENAI_API_KEY=sk-test123" in args
        assert "ANTHROPIC_API_KEY=ant-key456" in args
        # OPENROUTER not set, should not appear
        assert not any("OPENROUTER" in a for a in args)

    def test_no_keys_returns_empty(self, monkeypatch):
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        assert _api_key_env_args() == []


# ---------------------------------------------------------------------------
# Test: Default options
# ---------------------------------------------------------------------------


class TestRunDefaults:
    """Verify default option values for the run command."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_default_timeout_3600(self, mock_stage, mock_subprocess, runner, tmp_path):
        """Default timeout should be 3600 seconds."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = runner.invoke(main, ["run", "--image", "test-img"])
        # The command should have been called with --stop-timeout 3600
        call_args = mock_subprocess.call_args[0][0]
        idx = call_args.index("--stop-timeout")
        assert call_args[idx + 1] == "3600"


# ---------------------------------------------------------------------------
# Test: Harvest logic
# ---------------------------------------------------------------------------


class TestHarvest:
    """Harvest should copy artifacts from workspace to results dir."""

    def test_harvest_signature_no_cards_dir(self):
        """_harvest_results should not accept a cards_dir parameter."""
        sig = inspect.signature(_harvest_results)
        assert "cards_dir" not in sig.parameters

    def test_harvests_modified_card_impls(self, tmp_path):
        """Modified card_impl.py files should be harvested."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Create workspace cards with modified content
        # Use real repo SOS card collector numbers
        repo_root = Path(__file__).resolve().parent.parent
        cards_dir = repo_root / "cards"
        sos_dir = cards_dir / "sos"
        assert sos_dir.exists(), f"SOS cards directory not found at {sos_dir}"
        # Pick the first SOS card
        first_card = next(
            (d for d in sorted(sos_dir.iterdir()) if d.is_dir() and (d / "card_spec.json").exists()),
            None,
        )
        assert first_card is not None, "No SOS card with card_spec.json found under cards/sos"

        cn = first_card.name
        ws_card = workspace / "cards" / "sos" / cn
        ws_card.mkdir(parents=True)
        (ws_card / "card_impl.py").write_text("# MODIFIED implementation\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", timed_out=False
        )

        assert (run_dir / "cards" / cn / "card_impl.py").exists()
        assert (run_dir / "cards" / cn / "card_impl.py").read_text() == "# MODIFIED implementation\n"

    def test_harvests_output_logs(self, tmp_path):
        """progress.jsonl, stdout.log, stderr.log should be harvested."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        (output / "progress.jsonl").write_text('{"card": "1"}\n')
        (output / "stdout.log").write_text("stdout content\n")
        (output / "stderr.log").write_text("stderr content\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", timed_out=False
        )

        assert (run_dir / "progress.jsonl").read_text() == '{"card": "1"}\n'
        assert (run_dir / "stdout.log").read_text() == "stdout content\n"
        assert (run_dir / "stderr.log").read_text() == "stderr content\n"

    def test_engine_diff_generation(self, tmp_path):
        """If engine_work differs from engine, generate engine_diff.patch."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Create engine dirs with differences
        engine_orig = workspace / "engine"
        engine_work = workspace / "engine_work"
        engine_orig.mkdir()
        engine_work.mkdir()
        (engine_orig / "base.py").write_text("original\n")
        (engine_work / "base.py").write_text("modified\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", timed_out=False
        )

        patch_file = run_dir / "engine_diff.patch"
        assert patch_file.exists()
        content = patch_file.read_text()
        assert "original" in content or "modified" in content


# ---------------------------------------------------------------------------
# Test: Card status detection
# ---------------------------------------------------------------------------


class TestCardStatus:
    """Card status should reflect whether card_impl.py was modified."""

    def test_missing_cards_get_no_output(self, tmp_path):
        """Cards without workspace card_impl.py → no_output."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        run_dir = _harvest_results(
            workspace, output, results, "test-run", timed_out=False
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses, "status.json should contain at least one card entry"
        # All SOS cards should be no_output since none exist in workspace
        for status in statuses.values():
            assert status == "no_output"

    def test_timeout_unmodified_cards_get_timeout_status(self, tmp_path):
        """When timed_out=True, missing cards → timeout."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        run_dir = _harvest_results(
            workspace, output, results, "test-run", timed_out=True
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses, "status.json should contain at least one card entry"
        # All should be timeout since none are modified
        for status in statuses.values():
            assert status == "timeout"


# ---------------------------------------------------------------------------
# Test: Timeout handling
# ---------------------------------------------------------------------------


class TestTimeout:
    """When Docker container times out, partial harvest should still happen."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_timeout_still_harvests(self, mock_stage, mock_subprocess, runner, tmp_path):
        """TimeoutExpired should trigger harvest with timed_out=True."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        # Create a modified card in workspace
        ws_card = workspace / "cards" / "sos" / "1"
        ws_card.mkdir(parents=True)
        (ws_card / "card_impl.py").write_text("# modified\n")

        mock_stage.return_value = (workspace, output)
        mock_subprocess.side_effect = subprocess.TimeoutExpired("docker", 3600)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img",
             "--results-dir", str(tmp_path / "results")],
        )

        # Should mention timeout
        assert "timed out" in result.output.lower() or "timeout" in result.output.lower()
        # Should still harvest
        assert "harvest" in result.output.lower() or "results saved" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Smoke command — pass case
# ---------------------------------------------------------------------------


class TestSmokePass:
    """Smoke command pass case: exit 0 + hello.py exists."""

    @patch("silverquillm.cli.subprocess.run")
    def test_smoke_pass(self, mock_subprocess, runner, tmp_path):
        """PASS when container exits 0 and hello.py exists."""
        mock_subprocess.return_value = MagicMock(returncode=0)

        # We need to create hello.py in the workspace during the "docker run"
        # Since we mock subprocess, we simulate it via side_effect
        def create_hello(*args, **kwargs):
            # Extract workspace path from the -v arg
            cmd = args[0]
            for i, arg in enumerate(cmd):
                if arg == "-v" and "/workspace" in cmd[i + 1]:
                    ws_path = cmd[i + 1].split(":")[0]
                    (Path(ws_path) / "hello.py").write_text("print('Hello World')\n")
                    break
            return MagicMock(returncode=0)

        mock_subprocess.side_effect = create_hello

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "PASS" in result.output

    @patch("silverquillm.cli.subprocess.run")
    def test_smoke_fail_no_hello(self, mock_subprocess, runner):
        """FAIL when container exits 0 but no hello.py."""
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "FAIL" in result.output
        assert "hello.py" in result.output.lower()

    @patch("silverquillm.cli.subprocess.run")
    def test_smoke_fail_nonzero_exit(self, mock_subprocess, runner):
        """FAIL when container exits non-zero."""
        mock_subprocess.return_value = MagicMock(returncode=1)

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "FAIL" in result.output
        assert "exit code" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Run command invokes docker with correct args
# ---------------------------------------------------------------------------


class TestRunDockerArgs:
    """Verify docker command is constructed correctly."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_command_contains_image(self, mock_stage, mock_subprocess, runner, tmp_path):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = runner.invoke(main, ["run", "--image", "my-img:v1"])
        call_args = mock_subprocess.call_args[0][0]
        assert "my-img:v1" in call_args
        assert "docker" in call_args[0]

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_mounts_workspace_and_output(self, mock_stage, mock_subprocess, runner, tmp_path):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = runner.invoke(main, ["run", "--image", "my-img"])
        call_args = mock_subprocess.call_args[0][0]
        # Should have -v for workspace and output
        v_args = [call_args[i + 1] for i, a in enumerate(call_args) if a == "-v"]
        assert any("/workspace" in v for v in v_args)
        assert any("/output" in v for v in v_args)

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_api_keys_in_docker_command(self, mock_stage, mock_subprocess, runner, tmp_path, monkeypatch):
        """Set API keys should be passed as -e args to docker."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = runner.invoke(main, ["run", "--image", "my-img"])
        call_args = mock_subprocess.call_args[0][0]
        assert "OPENAI_API_KEY=sk-test" in call_args


# ---------------------------------------------------------------------------
# Test: run_manifest.json — writing and harvesting
# ---------------------------------------------------------------------------


class TestRunManifest:
    """run_manifest.json should be written during staging and harvested."""

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_written_before_docker_run(self, mock_stage, mock_subprocess, runner, tmp_path):
        """run_manifest.json should exist in workspace after staging."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "300"])

        manifest_path = workspace / "run_manifest.json"
        assert manifest_path.exists(), "run_manifest.json should be written to workspace"

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_is_valid_json(self, mock_stage, mock_subprocess, runner, tmp_path):
        """run_manifest.json must be valid JSON."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "600"])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        assert isinstance(manifest, dict)

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_has_timeout_seconds_int(self, mock_stage, mock_subprocess, runner, tmp_path):
        """timeout_seconds must be an int matching the --timeout flag."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "420"])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        assert "timeout_seconds" in manifest
        assert isinstance(manifest["timeout_seconds"], int)
        assert manifest["timeout_seconds"] == 420

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_has_deadline_utc_iso8601(self, mock_stage, mock_subprocess, runner, tmp_path):
        """deadline_utc must be an ISO-8601 string ending in 'Z'."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "300"])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        assert "deadline_utc" in manifest
        deadline = manifest["deadline_utc"]
        assert isinstance(deadline, str)
        assert deadline.endswith("Z"), f"deadline_utc should end with 'Z', got: {deadline}"
        # Verify it's parseable as ISO-8601
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_has_exactly_two_fields(self, mock_stage, mock_subprocess, runner, tmp_path):
        """run_manifest.json must contain exactly two fields."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "300"])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        assert set(manifest.keys()) == {"timeout_seconds", "deadline_utc"}

    def test_harvest_copies_manifest_to_results(self, tmp_path):
        """_harvest_results should copy run_manifest.json to run results dir."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Write a manifest in workspace
        manifest_data = {"timeout_seconds": 300, "deadline_utc": "2025-01-01T00:05:00Z"}
        (workspace / "run_manifest.json").write_text(json.dumps(manifest_data))

        run_dir = _harvest_results(workspace, output, results, "test-run", timed_out=False)

        harvested = run_dir / "run_manifest.json"
        assert harvested.exists(), "run_manifest.json should be copied to results"
        assert json.loads(harvested.read_text()) == manifest_data

    def test_harvest_without_manifest_does_not_crash(self, tmp_path):
        """_harvest_results should not fail if run_manifest.json is absent."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # No manifest written — should not raise
        run_dir = _harvest_results(workspace, output, results, "test-run", timed_out=False)
        assert not (run_dir / "run_manifest.json").exists()
