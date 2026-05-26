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

from silverquillm.cli import main, _make_run_name, _image_dir, _image_results_dir, _api_key_env_args, _harvest_results, _rewrite_diff_headers
from silverquillm.runner import LifecycleResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _patch_run_dependencies():
    """Auto-mock build_card_name_map and post-run functions for all tests.

    These were added in Items 6-8 and break older CLI tests that mock only
    stage_workspace + ContainerLifecycle.
    """
    with patch("silverquillm.cli.build_card_name_map", return_value={}), \
         patch("silverquillm.cli._evaluate_results"), \
         patch("silverquillm.cli._generate_run_summary"):
        yield


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
    """Run names should match {set_code}-{image_dir}-{ISO-timestamp} pattern."""

    def test_default_set_code(self):
        """Calling _make_run_name('sos') should use 'sos-' prefix."""
        name = _make_run_name("sos")
        assert name.startswith("sos-"), f"Expected 'sos-' prefix, got: {name}"
        # Check ISO timestamp portion: YYYY-MM-DDTHH-MM
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}", name)

    def test_custom_set_code(self):
        """Calling _make_run_name('fdn') should use 'fdn-' prefix."""
        name = _make_run_name("fdn")
        assert name.startswith("fdn-"), f"Expected 'fdn-' prefix, got: {name}"
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}", name)

    def test_timestamp_format(self):
        """Timestamp should be ISO format with hyphens replacing colons."""
        name = _make_run_name("sos")
        # Full pattern: {set_code}-{image_dir}-YYYY-MM-DDTHH-MM (optional nonce)
        assert re.match(r"^sos-[^-]+-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}(-[0-9a-f]+)?$", name)

    def test_image_default_parameter(self):
        """The default image parameter value should be 'default'."""
        sig = inspect.signature(_make_run_name)
        default = sig.parameters["image"].default
        assert default == "default"

    def test_image_dir_in_run_name(self):
        """Image dir should appear between set_code and timestamp."""
        name = _make_run_name("sos", image="silverquillm-pi-blind:latest")
        assert name.startswith("sos-pi-blind-"), f"Expected 'sos-pi-blind-' prefix, got: {name}"


# ---------------------------------------------------------------------------
# Test: _image_dir helper
# ---------------------------------------------------------------------------


class TestImageDir:
    """_image_dir strips silverquillm- prefix and :tag suffix."""

    def test_silverquillm_prefix_with_tag(self):
        assert _image_dir("silverquillm-local-pi-blind:latest") == "local-pi-blind"

    def test_registry_with_silverquillm_prefix(self):
        assert _image_dir("ghcr.io/user/silverquillm-pi-blind:latest") == "pi-blind"

    def test_custom_image_no_prefix(self):
        assert _image_dir("my-custom-image:v2") == "my-custom-image"

    def test_plain_image_no_tag(self):
        assert _image_dir("silverquillm-foo") == "foo"

    def test_no_prefix_no_tag(self):
        assert _image_dir("some-image") == "some-image"


# ---------------------------------------------------------------------------
# Test: _image_results_dir helper
# ---------------------------------------------------------------------------


class TestImageResultsDir:
    """_image_results_dir returns repo_root/docker/{image_dir}/results."""

    def test_silverquillm_local_pi_blind(self):
        result = _image_results_dir("silverquillm-local-pi-blind:latest")
        assert result.parts[-3:] == ("docker", "local-pi-blind", "results")

    def test_custom_image(self):
        result = _image_results_dir("my-custom-image:v2")
        assert result.parts[-3:] == ("docker", "my-custom-image", "results")

    def test_registry_image(self):
        result = _image_results_dir("ghcr.io/user/silverquillm-pi-blind:latest")
        assert result.parts[-3:] == ("docker", "pi-blind", "results")

    def test_returns_path_object(self):
        result = _image_results_dir("silverquillm-foo:v1")
        assert isinstance(result, Path)


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
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "COPILOT_GITHUB_TOKEN"):
            monkeypatch.delenv(key, raising=False)
        assert _api_key_env_args() == []


# ---------------------------------------------------------------------------
# Test: Default options
# ---------------------------------------------------------------------------


class TestRunDefaults:
    """Verify default option values for the run command."""

    @patch("silverquillm.cli._harvest_results")
    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_default_timeout_3600(self, mock_stage, mock_lifecycle_cls, mock_harvest, runner, tmp_path):
        """Default timeout should be 3600 seconds."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        output = tmp_path / "output"
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance
        mock_harvest.return_value = tmp_path / "results" / "run"

        result = runner.invoke(main, ["run", "--image", "test-img", "--results-dir", str(tmp_path / "results")])
        # ContainerLifecycle should have been called with hard_timeout=3600
        call_kwargs = mock_lifecycle_cls.call_args
        assert call_kwargs.kwargs.get("hard_timeout", call_kwargs[1].get("hard_timeout")) == 3600


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
        cards_dir = repo_root / "benchmarks" / "sos" / "workspace" / "cards"
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
        """docker_stdout.log, docker_stderr.log, and *.jsonl should be harvested (progress.jsonl excluded)."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        (output / "progress.jsonl").write_text('{"card": "1"}\n')
        (output / "fast_telemetry.jsonl").write_text('{"edit": true}\n')
        (output / "docker_stdout.log").write_text("stdout content\n")
        (output / "docker_stderr.log").write_text("stderr content\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", timed_out=False
        )

        assert not (run_dir / "progress.jsonl").exists()
        assert (run_dir / "fast_telemetry.jsonl").read_text() == '{"edit": true}\n'
        assert (run_dir / "docker_stdout.log").read_text() == "stdout content\n"
        assert (run_dir / "docker_stderr.log").read_text() == "stderr content\n"

    def test_engine_diff_generation(self, tmp_path):
        """If workspace engine differs from repo engine, generate engine_diff.patch."""
        workspace = tmp_path / "ws" / "workspace"
        output = tmp_path / "ws" / "output"
        results = tmp_path / "results"
        workspace.mkdir(parents=True)
        output.mkdir(parents=True)

        # Create workspace engine dir with differences from repo engine
        engine_ws = workspace / "engine"
        engine_ws.mkdir()
        # We need the repo engine to exist for the diff to work
        # The diff is between _REPO_ROOT/engine and workspace/engine
        # Just verify the function doesn't crash; the actual diff depends on repo state
        (engine_ws / "extra_file.py").write_text("modified\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", timed_out=False
        )

        # engine_diff.patch should exist if repo engine exists and differs
        repo_root = Path(__file__).resolve().parent.parent
        if (repo_root / "engine").exists():
            patch_file = run_dir / "engine_diff.patch"
            assert patch_file.exists()
            content = patch_file.read_text()
            assert "modified" in content or "extra_file" in content


class TestRewriteDiffHeaders:
    """_rewrite_diff_headers converts absolute paths to a/<file> / b/<file>."""

    def test_strips_absolute_paths_from_headers(self):
        raw = (
            "diff -ruN /repo/engine/card.py /tmp/run_xyz/workspace/engine/card.py\n"
            "--- /repo/engine/card.py\t2026-05-25 16:43:11.728292087 +0000\n"
            "+++ /tmp/run_xyz/workspace/engine/card.py\t2026-05-26 00:11:01.765075517 +0000\n"
            "@@ -1,1 +1,1 @@\n"
            "-old line\n"
            "+new line\n"
        )
        out = _rewrite_diff_headers(raw, "/repo/engine", "/tmp/run_xyz/workspace/engine")
        assert "diff -ruN a/card.py b/card.py" in out
        assert "--- a/card.py" in out
        assert "+++ b/card.py" in out
        # Content lines untouched
        assert "-old line" in out
        assert "+new line" in out

    def test_handles_nested_paths(self):
        raw = (
            "diff -ruN /repo/engine/sub/card.py /tmp/ws/engine/sub/card.py\n"
            "--- /repo/engine/sub/card.py\n"
            "+++ /tmp/ws/engine/sub/card.py\n"
        )
        out = _rewrite_diff_headers(raw, "/repo/engine", "/tmp/ws/engine")
        assert "a/sub/card.py" in out
        assert "b/sub/card.py" in out

    def test_does_not_rewrite_content_lines(self):
        """Absolute paths that appear as patch content must not be rewritten."""
        raw = (
            "diff -ruN /repo/engine/card.py /tmp/ws/engine/card.py\n"
            "--- /repo/engine/card.py\n"
            "+++ /tmp/ws/engine/card.py\n"
            "@@ -1 +1 @@\n"
            '-PATH = "/repo/engine/card.py"\n'
            '+PATH = "/tmp/ws/engine/card.py"\n'
        )
        out = _rewrite_diff_headers(raw, "/repo/engine", "/tmp/ws/engine")
        assert '-PATH = "/repo/engine/card.py"' in out
        assert '+PATH = "/tmp/ws/engine/card.py"' in out


class TestRewrittenPatchApplies:
    """End-to-end: harvest produces a patch that `git apply -p1` accepts."""

    def test_rewritten_patch_applies_with_git(self, tmp_path):
        # Build a fake repo engine and a "workspace" engine with one tweaked file.
        repo_engine = tmp_path / "repo" / "engine"
        repo_engine.mkdir(parents=True)
        (repo_engine / "card.py").write_text("def foo():\n    return 1\n")

        ws_engine = tmp_path / "ws" / "engine"
        ws_engine.mkdir(parents=True)
        (ws_engine / "card.py").write_text("def foo():\n    return 2\n")

        raw = subprocess.run(
            ["diff", "-ruN", str(repo_engine), str(ws_engine)],
            capture_output=True, text=True,
        ).stdout
        patch_text = _rewrite_diff_headers(raw, str(repo_engine), str(ws_engine))

        # Stage a fresh baseline + apply with -p1 the way the evaluator does.
        staging = tmp_path / "staging" / "engine"
        staging.mkdir(parents=True)
        (staging / "card.py").write_text("def foo():\n    return 1\n")

        patch_file = tmp_path / "engine_diff.patch"
        patch_file.write_text(patch_text)

        result = subprocess.run(
            ["git", "apply", "-p1", str(patch_file)],
            cwd=str(staging),
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert (staging / "card.py").read_text() == "def foo():\n    return 2\n"


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
        for entry in statuses.values():
            status = entry["status"] if isinstance(entry, dict) else entry
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
        for entry in statuses.values():
            status = entry["status"] if isinstance(entry, dict) else entry
            assert status == "timeout"


# ---------------------------------------------------------------------------
# Test: Timeout handling
# ---------------------------------------------------------------------------


class TestTimeout:
    """When Docker container times out, partial harvest should still happen."""

    @patch("silverquillm.cli._harvest_results")
    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_timeout_still_harvests(self, mock_stage, mock_lifecycle_cls, mock_harvest, runner, tmp_path):
        """Timeout should trigger harvest with timed_out=True."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        # Create a modified card in workspace
        ws_card = workspace / "cards" / "sos" / "1"
        ws_card.mkdir(parents=True)
        (ws_card / "card_impl.py").write_text("# modified\n")

        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=None, timed_out=True, timeout_reason="hard_timeout", container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance
        mock_harvest.return_value = tmp_path / "results" / "run"

        result = runner.invoke(
            main,
            ["run", "--image", "test-img",
             "--results-dir", str(tmp_path / "results")],
        )

        # Should mention timeout
        assert "timed out" in result.output.lower() or "timeout" in result.output.lower()
        # Should still harvest
        assert mock_harvest.called


# ---------------------------------------------------------------------------
# Test: Smoke command — pass case
# ---------------------------------------------------------------------------


class TestSmokePass:
    """Smoke command pass case: exit 0 + hello.py exists."""

    @patch("silverquillm.cli.ContainerLifecycle")
    def test_smoke_pass(self, mock_lifecycle_cls, runner, tmp_path):
        """PASS when container exits 0 and hello.py exists."""
        def create_hello_side_effect(**kwargs):
            mock_instance = MagicMock()
            ws = kwargs.get("workspace", None)
            def run_side_effect():
                if ws:
                    (Path(ws) / "hello.py").write_text("print('Hello World')\n")
                return LifecycleResult(exit_code=0, timed_out=False, timeout_reason=None, container_name="test")
            mock_instance.run.side_effect = run_side_effect
            return mock_instance

        mock_lifecycle_cls.side_effect = create_hello_side_effect

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "PASS" in result.output

    @patch("silverquillm.cli.ContainerLifecycle")
    def test_smoke_fail_no_hello(self, mock_lifecycle_cls, runner):
        """FAIL when container exits 0 but no hello.py."""
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "FAIL" in result.output
        assert "hello.py" in result.output.lower()

    @patch("silverquillm.cli.ContainerLifecycle")
    def test_smoke_fail_nonzero_exit(self, mock_lifecycle_cls, runner):
        """FAIL when container exits non-zero."""
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=1, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        result = runner.invoke(main, ["smoke", "--image", "test-img"])
        assert "FAIL" in result.output
        assert "exit code" in result.output.lower()


# ---------------------------------------------------------------------------
# Test: Run command invokes docker with correct args
# ---------------------------------------------------------------------------


class TestRunDockerArgs:
    """Verify ContainerLifecycle is constructed correctly."""

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_command_contains_image(self, mock_stage, mock_lifecycle_cls, runner, tmp_path):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        result = runner.invoke(main, ["run", "--image", "my-img:v1", "--results-dir", str(tmp_path / "results")])
        call_kwargs = mock_lifecycle_cls.call_args
        assert call_kwargs.kwargs.get("image") == "my-img:v1"

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_docker_mounts_workspace_and_output(self, mock_stage, mock_lifecycle_cls, runner, tmp_path):
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        result = runner.invoke(main, ["run", "--image", "my-img", "--results-dir", str(tmp_path / "results")])
        call_kwargs = mock_lifecycle_cls.call_args
        assert call_kwargs.kwargs.get("workspace") == workspace
        assert call_kwargs.kwargs.get("output") == output

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_api_keys_in_docker_command(self, mock_stage, mock_lifecycle_cls, runner, tmp_path, monkeypatch):
        """Set API keys should be passed as env_args to ContainerLifecycle."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        result = runner.invoke(main, ["run", "--image", "my-img", "--results-dir", str(tmp_path / "results")])
        call_kwargs = mock_lifecycle_cls.call_args
        env_args = call_kwargs.kwargs.get("env_args", [])
        assert "OPENAI_API_KEY=sk-test" in env_args


# ---------------------------------------------------------------------------
# Test: run_manifest.json — writing and harvesting
# ---------------------------------------------------------------------------


class TestRunManifest:
    """run_manifest.json should be written during staging and harvested."""

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_written_before_docker_run(self, mock_stage, mock_lifecycle_cls, runner, tmp_path):
        """run_manifest.json should exist in workspace after staging."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "300", "--results-dir", str(tmp_path / "results")])

        manifest_path = workspace / "run_manifest.json"
        assert manifest_path.exists(), "run_manifest.json should be written to workspace"

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_is_valid_json(self, mock_stage, mock_lifecycle_cls, runner, tmp_path):
        """run_manifest.json must be valid JSON."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "600", "--results-dir", str(tmp_path / "results")])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        assert isinstance(manifest, dict)

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_has_timeout_seconds_int(self, mock_stage, mock_lifecycle_cls, runner, tmp_path):
        """timeout_seconds must be an int matching the --timeout flag."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "420", "--results-dir", str(tmp_path / "results")])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        assert "timeout_seconds" in manifest
        assert isinstance(manifest["timeout_seconds"], int)
        assert manifest["timeout_seconds"] == 420

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_has_deadline_utc_iso8601(self, mock_stage, mock_lifecycle_cls, runner, tmp_path):
        """deadline_utc must be an ISO-8601 string ending in 'Z'."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "300", "--results-dir", str(tmp_path / "results")])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        assert "deadline_utc" in manifest
        deadline = manifest["deadline_utc"]
        assert isinstance(deadline, str)
        assert deadline.endswith("Z"), f"deadline_utc should end with 'Z', got: {deadline}"
        # Verify it's parseable as ISO-8601
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    @patch("silverquillm.cli.ContainerLifecycle")
    @patch("silverquillm.cli.stage_workspace")
    def test_manifest_has_required_fields(self, mock_stage, mock_lifecycle_cls, runner, tmp_path):
        """run_manifest.json must include the audit-trail fields resume reads.

        Per ADR-009 the manifest is the source of truth for ``docker_image``
        and ``card_filter`` (read at resume-staging time). The advisory
        timeout fields remain required.
        """
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_instance = MagicMock()
        mock_instance.run.return_value = LifecycleResult(
            exit_code=0, timed_out=False, timeout_reason=None, container_name="test"
        )
        mock_lifecycle_cls.return_value = mock_instance

        runner.invoke(main, ["run", "--image", "test-img", "--timeout", "300", "--results-dir", str(tmp_path / "results")])

        manifest = json.loads((workspace / "run_manifest.json").read_text())
        required = {"timeout_seconds", "deadline_utc", "docker_image", "card_filter", "benchmark_set"}
        assert required.issubset(manifest.keys())
        assert manifest["docker_image"] == "test-img"

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
