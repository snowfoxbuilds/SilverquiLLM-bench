"""Tests for silverquillm.cli — run and smoke Docker commands."""

from __future__ import annotations

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


@pytest.fixture()
def cards_dir(tmp_path: Path) -> Path:
    """Create a minimal cards directory with a couple of SOS cards."""
    sos = tmp_path / "cards" / "sos"
    for cn in ("1", "2", "3"):
        card_dir = sos / cn
        card_dir.mkdir(parents=True)
        (card_dir / "card_spec.json").write_text(
            json.dumps({
                "name": f"Card {cn}",
                "collector_number": cn,
                "set_code": "sos",
                "mana_cost": "{1}",
                "type_line": "Creature",
                "oracle_text": "Test",
                "complexity_tier": "T1",
            }),
            encoding="utf-8",
        )
        # Template card_impl.py (identical content)
        (card_dir / "card_impl.py").write_text(
            f'"""Card {cn} implementation."""\n\nclass Card{cn}:\n    pass\n',
            encoding="utf-8",
        )
    return tmp_path / "cards"


@pytest.fixture()
def engine_dir(tmp_path: Path) -> Path:
    """Create a minimal engine directory."""
    eng = tmp_path / "engine"
    eng.mkdir(parents=True)
    (eng / "base.py").write_text("# engine base\n", encoding="utf-8")
    return eng


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

    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_default_timeout_3600(self, mock_stage, mock_popen, runner, tmp_path):
        """Default timeout should be 3600 seconds."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        result = runner.invoke(main, ["run", "--image", "test-img"])
        # The command should have been called with --stop-timeout 3600
        call_args = mock_popen.call_args[0][0]
        idx = call_args.index("--stop-timeout")
        assert call_args[idx + 1] == "3600"


# ---------------------------------------------------------------------------
# Test: Harvest logic
# ---------------------------------------------------------------------------


class TestHarvest:
    """Harvest should copy artifacts from workspace to results dir."""

    def test_harvests_modified_card_impls(self, tmp_path, cards_dir):
        """Modified card_impl.py files should be harvested."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Create workspace cards with modified content for card "1"
        ws_card = workspace / "cards" / "sos" / "1"
        ws_card.mkdir(parents=True)
        (ws_card / "card_impl.py").write_text("# MODIFIED implementation\n")

        # Card "2" stays as template (same as original)
        ws_card2 = workspace / "cards" / "sos" / "2"
        ws_card2.mkdir(parents=True)
        (ws_card2 / "card_impl.py").write_text(
            '"""Card 2 implementation."""\n\nclass Card2:\n    pass\n'
        )

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert (run_dir / "cards" / "1" / "card_impl.py").exists()
        assert (run_dir / "cards" / "1" / "card_impl.py").read_text() == "# MODIFIED implementation\n"

    def test_harvests_output_logs(self, tmp_path, cards_dir):
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
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert (run_dir / "progress.jsonl").read_text() == '{"card": "1"}\n'
        assert (run_dir / "stdout.log").read_text() == "stdout content\n"
        assert (run_dir / "stderr.log").read_text() == "stderr content\n"

    def test_engine_diff_generation(self, tmp_path, cards_dir):
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
            workspace, output, results, "test-run", cards_dir, timed_out=False
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

    def test_unmodified_cards_get_no_output(self, tmp_path, cards_dir):
        """Cards identical to template → no_output status."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Card "1": identical to template
        ws_card = workspace / "cards" / "sos" / "1"
        ws_card.mkdir(parents=True)
        original_content = (cards_dir / "sos" / "1" / "card_impl.py").read_text()
        (ws_card / "card_impl.py").write_text(original_content)

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses["1"] == "no_output"

    def test_modified_cards_get_completed(self, tmp_path, cards_dir):
        """Cards different from template → completed status."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Card "2": modified
        ws_card = workspace / "cards" / "sos" / "2"
        ws_card.mkdir(parents=True)
        (ws_card / "card_impl.py").write_text("# totally new impl\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses["2"] == "completed"

    def test_missing_cards_get_no_output(self, tmp_path, cards_dir):
        """Cards without workspace card_impl.py → no_output."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses["1"] == "no_output"
        assert statuses["2"] == "no_output"
        assert statuses["3"] == "no_output"

    def test_timeout_cards_get_timeout_status(self, tmp_path, cards_dir):
        """When timed_out=True, unmodified/missing cards → timeout."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Card "1": modified (still completed even on timeout)
        ws_card = workspace / "cards" / "sos" / "1"
        ws_card.mkdir(parents=True)
        (ws_card / "card_impl.py").write_text("# modified\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=True
        )

        statuses = json.loads((run_dir / "status.json").read_text())
        assert statuses["1"] == "completed"
        assert statuses["2"] == "timeout"
        assert statuses["3"] == "timeout"


# ---------------------------------------------------------------------------
# Test: Timeout handling
# ---------------------------------------------------------------------------


class TestTimeout:
    """When Docker container times out, partial harvest should still happen."""

    @patch("silverquillm.cli._stop_container")
    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_timeout_still_harvests(self, mock_stage, mock_popen, mock_stop, runner, tmp_path, cards_dir):
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
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        # First wait() raises TimeoutExpired, second wait() (after docker stop) succeeds
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired("docker", 3600), None]
        mock_popen.return_value = mock_proc

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards-dir", str(cards_dir),
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

    @patch("silverquillm.cli.subprocess.Popen")
    def test_smoke_pass(self, mock_popen, runner, tmp_path):
        """PASS when container exits 0 and hello.py exists."""
        # We need to create hello.py in the workspace during the "docker run"
        # Since we mock Popen, we simulate it via side_effect on constructor
        def create_hello(cmd, **kwargs):
            # Extract workspace path from the -v arg
            for i, arg in enumerate(cmd):
                if arg == "-v" and "/workspace" in cmd[i + 1]:
                    ws_path = cmd[i + 1].split(":")[0]
                    (Path(ws_path) / "hello.py").write_text("print('Hello World')\n")
                    break
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.wait.return_value = None
            return mock_proc

        mock_popen.side_effect = create_hello

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "PASS" in result.output

    @patch("silverquillm.cli.subprocess.Popen")
    def test_smoke_fail_no_hello(self, mock_popen, runner):
        """FAIL when container exits 0 but no hello.py."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "FAIL" in result.output
        assert "hello.py" in result.output.lower()

    @patch("silverquillm.cli.subprocess.Popen")
    def test_smoke_fail_nonzero_exit(self, mock_popen, runner):
        """FAIL when container exits non-zero."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "FAIL" in result.output
        assert "exit code" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Run command invokes docker with correct args
# ---------------------------------------------------------------------------


class TestRunDockerArgs:
    """Verify docker command is constructed correctly."""

    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_command_contains_image(self, mock_stage, mock_popen, runner, tmp_path):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        result = runner.invoke(main, ["run", "--image", "my-img:v1"])
        call_args = mock_popen.call_args[0][0]
        assert "my-img:v1" in call_args
        assert "docker" in call_args[0]

    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_mounts_workspace_and_output(self, mock_stage, mock_popen, runner, tmp_path):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        result = runner.invoke(main, ["run", "--image", "my-img"])
        call_args = mock_popen.call_args[0][0]
        # Should have -v for workspace and output
        v_args = [call_args[i + 1] for i, a in enumerate(call_args) if a == "-v"]
        assert any("/workspace" in v for v in v_args)
        assert any("/output" in v for v in v_args)

    @patch("silverquillm.cli.subprocess.Popen")
    @patch("silverquillm.cli.stage_workspace")
    def test_api_keys_in_docker_command(self, mock_stage, mock_popen, runner, tmp_path, monkeypatch):
        """Set API keys should be passed as -e args to docker."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        result = runner.invoke(main, ["run", "--image", "my-img"])
        call_args = mock_popen.call_args[0][0]
        assert "OPENAI_API_KEY=sk-test" in call_args
