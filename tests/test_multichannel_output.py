"""Tests for multi-channel output capture (TODO Item 2).

Covers:
- _harvest_results copies all .log files, progress.jsonl, and exit_code
- format_log_lines produces correctly tagged and colored output
- _parse_log_lines sorts by timestamp across channels
- logs CLI command behavior (happy path, missing dir, no-color)
- Edge cases: missing log files, empty log files, mixed timestamps
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from silverquillm.cli import (
    _harvest_results,
    format_log_lines,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def cards_dir(tmp_path: Path) -> Path:
    """Minimal cards directory with one SOS card."""
    sos = tmp_path / "cards" / "sos"
    for cn in ("1",):
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
        (card_dir / "card_impl.py").write_text(
            f'"""Card {cn} implementation."""\n\nclass Card{cn}:\n    pass\n',
            encoding="utf-8",
        )
    return tmp_path / "cards"


@pytest.fixture()
def harvest_dirs(tmp_path: Path):
    """Create workspace, output, and results dirs for harvest tests."""
    workspace = tmp_path / "ws" / "workspace"
    output = tmp_path / "ws" / "output"
    results = tmp_path / "results"
    workspace.mkdir(parents=True)
    output.mkdir(parents=True)
    return workspace, output, results


# ---------------------------------------------------------------------------
# Harvest: multi-channel log files
# ---------------------------------------------------------------------------


class TestHarvestMultiChannel:
    """_harvest_results should copy all structured log files."""

    def test_copies_system_log(self, harvest_dirs, cards_dir):
        """system.log should be copied to run results."""
        workspace, output, results = harvest_dirs
        (output / "system.log").write_text("[10:00:00] engine copy done\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert (run_dir / "system.log").read_text() == "[10:00:00] engine copy done\n"

    def test_copies_agent_stdout_log(self, harvest_dirs, cards_dir):
        """agent_stdout.log should be copied to run results."""
        workspace, output, results = harvest_dirs
        (output / "agent_stdout.log").write_text("tool call output\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert (run_dir / "agent_stdout.log").read_text() == "tool call output\n"

    def test_copies_agent_stderr_log(self, harvest_dirs, cards_dir):
        """agent_stderr.log should be copied to run results."""
        workspace, output, results = harvest_dirs
        (output / "agent_stderr.log").write_text("thinking...\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert (run_dir / "agent_stderr.log").read_text() == "thinking...\n"

    def test_copies_progress_jsonl(self, harvest_dirs, cards_dir):
        """progress.jsonl should be copied to run results."""
        workspace, output, results = harvest_dirs
        (output / "progress.jsonl").write_text('{"event":"started"}\n')

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert (run_dir / "progress.jsonl").read_text() == '{"event":"started"}\n'

    def test_copies_exit_code(self, harvest_dirs, cards_dir):
        """exit_code file should be copied to run results."""
        workspace, output, results = harvest_dirs
        (output / "exit_code").write_text("0\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert (run_dir / "exit_code").read_text() == "0\n"

    def test_copies_all_log_files_together(self, harvest_dirs, cards_dir):
        """All multi-channel log files present together should all be copied."""
        workspace, output, results = harvest_dirs

        expected_files = {
            "system.log": "sys content\n",
            "agent_stdout.log": "stdout content\n",
            "agent_stderr.log": "stderr content\n",
            "progress.jsonl": '{"event":"done"}\n',
            "exit_code": "0\n",
        }
        for name, content in expected_files.items():
            (output / name).write_text(content)

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        for name, content in expected_files.items():
            assert (run_dir / name).exists(), f"{name} should be harvested"
            assert (run_dir / name).read_text() == content

    def test_does_not_copy_non_log_files(self, harvest_dirs, cards_dir):
        """Arbitrary files without .log extension should NOT be harvested."""
        workspace, output, results = harvest_dirs
        (output / "random.txt").write_text("nope\n")
        (output / "data.json").write_text("{}\n")

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert not (run_dir / "random.txt").exists()
        assert not (run_dir / "data.json").exists()

    def test_handles_empty_output_dir(self, harvest_dirs, cards_dir):
        """Empty output directory should not crash harvest."""
        workspace, output, results = harvest_dirs

        run_dir = _harvest_results(
            workspace, output, results, "test-run", cards_dir, timed_out=False
        )

        assert run_dir.is_dir()


# ---------------------------------------------------------------------------
# format_log_lines
# ---------------------------------------------------------------------------


class TestFormatLogLines:
    """format_log_lines should tag lines by channel with optional color."""

    def test_tags_system_log_lines(self, tmp_path):
        """system.log lines should be tagged [system]."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:00] engine copy\n")

        lines = format_log_lines(run_dir, color=False)

        assert len(lines) == 1
        assert lines[0] == "[system] [10:00:00] engine copy"

    def test_tags_agent_stdout_lines(self, tmp_path):
        """agent_stdout.log lines should be tagged [agent_stdout]."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "agent_stdout.log").write_text("file created\n")

        lines = format_log_lines(run_dir, color=False)

        assert len(lines) == 1
        assert lines[0] == "[agent_stdout] file created"

    def test_tags_agent_stderr_lines(self, tmp_path):
        """agent_stderr.log lines should be tagged [agent_stderr]."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "agent_stderr.log").write_text("reasoning step\n")

        lines = format_log_lines(run_dir, color=False)

        assert len(lines) == 1
        assert lines[0] == "[agent_stderr] reasoning step"

    def test_tags_progress_lines(self, tmp_path):
        """progress.jsonl lines should be tagged [progress]."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "progress.jsonl").write_text('{"event":"started"}\n')

        lines = format_log_lines(run_dir, color=False)

        assert len(lines) == 1
        assert lines[0] == '[progress] {"event":"started"}'

    def test_colored_output_includes_ansi_codes(self, tmp_path):
        """With color=True, lines should contain ANSI escape sequences."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:00] test\n")

        lines = format_log_lines(run_dir, color=True)

        assert len(lines) == 1
        # Blue ANSI for system
        assert "\033[34m" in lines[0]
        # Reset at end
        assert "\033[0m" in lines[0]

    def test_no_color_has_no_ansi(self, tmp_path):
        """With color=False, lines should NOT contain ANSI escape sequences."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:00] test\n")

        lines = format_log_lines(run_dir, color=False)

        assert "\033[" not in lines[0]

    def test_interleaves_by_timestamp(self, tmp_path):
        """Lines from different channels with timestamps should interleave chronologically."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text(
            "[10:00:01] sys first\n[10:00:03] sys third\n"
        )
        (run_dir / "agent_stdout.log").write_text(
            "[10:00:02] agent second\n"
        )

        lines = format_log_lines(run_dir, color=False)

        assert len(lines) == 3
        assert "sys first" in lines[0]
        assert "agent second" in lines[1]
        assert "sys third" in lines[2]

    def test_empty_log_files_produce_no_output(self, tmp_path):
        """Empty log files should produce no output lines."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("")

        lines = format_log_lines(run_dir, color=False)

        assert lines == []

    def test_missing_log_files_produce_no_output(self, tmp_path):
        """If no log files exist, output should be empty."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        lines = format_log_lines(run_dir, color=False)

        assert lines == []

    def test_multiline_files_all_tagged(self, tmp_path):
        """Every line in a multi-line log file should get the channel tag."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("line1\nline2\nline3\n")

        lines = format_log_lines(run_dir, color=False)

        assert len(lines) == 3
        for line in lines:
            assert line.startswith("[system] ")

    def test_progress_jsonl_timestamp_sorting(self, tmp_path):
        """progress.jsonl lines with ISO 'ts' field should sort by timestamp."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:05] after progress\n")
        (run_dir / "progress.jsonl").write_text(
            json.dumps({"event": "started", "ts": "2024-01-01T10:00:01Z"}) + "\n"
        )

        lines = format_log_lines(run_dir, color=False)

        assert len(lines) == 2
        # progress line has earlier timestamp → should come first
        assert "progress" in lines[0].split("]")[0]
        assert "system" in lines[1].split("]")[0]

    def test_color_channels_are_distinct(self, tmp_path):
        """Each channel should use a different ANSI color code."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("sys\n")
        (run_dir / "agent_stderr.log").write_text("err\n")
        (run_dir / "agent_stdout.log").write_text("out\n")
        (run_dir / "progress.jsonl").write_text('{"event":"x"}\n')

        lines = format_log_lines(run_dir, color=True)

        # Extract ANSI color code from each line
        colors = set()
        for line in lines:
            # Color code is at the start: \033[XXm
            if "\033[" in line:
                code = line.split("m")[0] + "m"
                colors.add(code)

        # All 4 channels should have distinct colors
        assert len(colors) == 4


# ---------------------------------------------------------------------------
# CLI: logs command
# ---------------------------------------------------------------------------


class TestLogsCommand:
    """CLI `logs` command should display interleaved colored logs."""

    def test_logs_displays_output(self, runner, tmp_path):
        """logs --run should print formatted log lines."""
        run_dir = tmp_path / "my-run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:00] started\n")

        result = runner.invoke(
            main, ["logs", "--run", "my-run", "--results-dir", str(tmp_path), "--no-color"]
        )

        assert result.exit_code == 0
        assert "[system] [10:00:00] started" in result.output

    def test_logs_error_on_missing_run_dir(self, runner, tmp_path):
        """logs should exit 1 if run directory doesn't exist."""
        result = runner.invoke(
            main, ["logs", "--run", "nonexistent", "--results-dir", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "not found" in result.output or "not found" in (result.output + (result.output or ""))

    def test_logs_error_on_empty_run_dir(self, runner, tmp_path):
        """logs should exit 1 if run directory has no log files."""
        run_dir = tmp_path / "empty-run"
        run_dir.mkdir()

        result = runner.invoke(
            main, ["logs", "--run", "empty-run", "--results-dir", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "No log files" in result.output or "no log" in result.output.lower()

    def test_logs_with_color(self, tmp_path):
        """logs without --no-color should include ANSI codes in format_log_lines.

        CliRunner strips ANSI by default, so we test via format_log_lines directly
        and verify the CLI wires color=True when --no-color is absent.
        """
        run_dir = tmp_path / "colored-run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:00] test\n")

        # Verify format_log_lines with color=True has ANSI codes
        lines = format_log_lines(run_dir, color=True)
        assert "\033[" in lines[0]

        # Verify CLI runs without error (color stripping is a CliRunner limitation)
        color_runner = CliRunner()
        result = color_runner.invoke(
            main, ["logs", "--run", "colored-run", "--results-dir", str(tmp_path)]
        )
        assert result.exit_code == 0

    def test_logs_no_color_flag(self, runner, tmp_path):
        """logs --no-color should produce output without ANSI codes."""
        run_dir = tmp_path / "plain-run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:00] test\n")

        result = runner.invoke(
            main, ["logs", "--run", "plain-run", "--results-dir", str(tmp_path), "--no-color"]
        )

        assert result.exit_code == 0
        assert "\033[" not in result.output

    def test_logs_multiple_channels_interleaved(self, runner, tmp_path):
        """logs should interleave multiple log channels in output."""
        run_dir = tmp_path / "multi-run"
        run_dir.mkdir()
        (run_dir / "system.log").write_text("[10:00:01] sys\n")
        (run_dir / "agent_stdout.log").write_text("[10:00:02] agent\n")

        result = runner.invoke(
            main, ["logs", "--run", "multi-run", "--results-dir", str(tmp_path), "--no-color"]
        )

        assert result.exit_code == 0
        output_lines = result.output.strip().split("\n")
        assert len(output_lines) == 2
        assert "sys" in output_lines[0]
        assert "agent" in output_lines[1]
