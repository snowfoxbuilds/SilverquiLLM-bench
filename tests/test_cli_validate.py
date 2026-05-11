"""Tests for CLI `benchmark validate` command (TODO item 11).

Tests the validate subcommand registered in silverquillm.cli, verifying:
- Single file and directory validation
- --report flag generates JSON with expected structure
- --cards filter
- --verbose flag output
- --stop-on-divergence flag
- Summary output format
- Error handling (invalid path, no JSON files, etc.)
- End-to-end with sample replay data
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from silverquillm.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_REPLAY = REPO_ROOT / "data" / "replays" / "sample_replay.json"
REPLAYS_DIR = REPO_ROOT / "data" / "replays"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_replay_path() -> str:
    return str(SAMPLE_REPLAY)


@pytest.fixture
def minimal_replay(tmp_path: Path) -> Path:
    """Create a minimal synthetic replay file."""
    replay = {
        "seat_id": 1,
        "opponent_seat_id": 2,
        "events": [
            {
                "gameStateMessage": {
                    "type": "GameStateType_Full",
                    "gameStateId": 1,
                    "gameObjects": [
                        {
                            "instanceId": 100,
                            "grpId": 95197,
                            "type": "GameObjectType_Card",
                            "zoneId": 10,
                            "ownerSeatId": 1,
                        }
                    ],
                    "zones": [
                        {
                            "zoneId": 10,
                            "type": "ZoneType_Hand",
                            "ownerSeatId": 1,
                            "objectInstanceIds": [100],
                        }
                    ],
                    "players": [
                        {"systemSeatNumber": 1, "lifeTotal": 20, "maxHandSize": 7},
                        {"systemSeatNumber": 2, "lifeTotal": 20, "maxHandSize": 7},
                    ],
                    "turnInfo": {"turnNumber": 1, "activePlayer": 1, "phase": "Phase_Beginning"},
                }
            }
        ],
    }
    replay_file = tmp_path / "test_replay.json"
    replay_file.write_text(json.dumps(replay))
    return replay_file


class TestValidateCommand:
    """Tests for `benchmark validate` subcommand."""

    def test_validate_command_exists(self, runner: CliRunner) -> None:
        """The validate subcommand should be registered."""
        result = runner.invoke(main, ["validate", "--help"])
        assert result.exit_code == 0
        assert "validate" in result.output.lower() or "REPLAY_PATH" in result.output

    def test_validate_help_shows_all_options(self, runner: CliRunner) -> None:
        """--help should list all CLI options."""
        result = runner.invoke(main, ["validate", "--help"])
        assert "--cards" in result.output
        assert "--verbose" in result.output
        assert "--report" in result.output
        assert "--stop-on-divergence" in result.output

    def test_validate_requires_replay_path(self, runner: CliRunner) -> None:
        """Invoking without REPLAY_PATH should fail."""
        result = runner.invoke(main, ["validate"])
        assert result.exit_code != 0


class TestValidateWithSingleFile:
    """Tests for validating a single replay file."""

    def test_validate_single_file_produces_summary(
        self, runner: CliRunner, sample_replay_path: str
    ) -> None:
        """Validating a single replay file should print summary output."""
        result = runner.invoke(main, ["validate", sample_replay_path])
        assert result.exit_code == 0
        assert "Games attempted" in result.output
        assert "Divergence rate" in result.output

    def test_validate_single_file_games_attempted_is_one(
        self, runner: CliRunner, sample_replay_path: str
    ) -> None:
        """A single file should report exactly 1 game attempted."""
        result = runner.invoke(main, ["validate", sample_replay_path])
        assert result.exit_code == 0
        assert "Games attempted: 1" in result.output


class TestValidateWithDirectory:
    """Tests for validating a directory of replay files."""

    def test_validate_directory(self, runner: CliRunner) -> None:
        """Validating the replays directory should process all replay files."""
        result = runner.invoke(main, ["validate", str(REPLAYS_DIR)])
        assert result.exit_code == 0
        assert "Games attempted" in result.output

    def test_validate_directory_excludes_card_id_map(
        self, runner: CliRunner
    ) -> None:
        """card_id_map.json should not be treated as a replay file."""
        result = runner.invoke(main, ["validate", str(REPLAYS_DIR)])
        assert result.exit_code == 0
        # Should not crash trying to parse card_id_map.json as a replay


class TestReportOption:
    """Tests for --report flag generating a JSON report."""

    def test_report_creates_json_file(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """--report should create a JSON file at the specified path."""
        report_file = tmp_path / "report.json"
        result = runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        assert result.exit_code == 0
        assert report_file.exists()
        data = json.loads(report_file.read_text())
        assert isinstance(data, dict)

    def test_report_has_required_fields(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """JSON report must contain games_attempted, divergences, per_card_rates."""
        report_file = tmp_path / "report.json"
        result = runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        assert result.exit_code == 0
        data = json.loads(report_file.read_text())
        assert "games_attempted" in data
        assert "divergences" in data
        assert "per_card_rates" in data

    def test_report_games_attempted_is_integer(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """games_attempted should be an integer."""
        report_file = tmp_path / "report.json"
        runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        data = json.loads(report_file.read_text())
        assert isinstance(data["games_attempted"], int)

    def test_report_divergences_is_list(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """divergences should be a list."""
        report_file = tmp_path / "report.json"
        runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        data = json.loads(report_file.read_text())
        assert isinstance(data["divergences"], list)

    def test_report_per_card_rates_is_dict(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """per_card_rates should be a dict."""
        report_file = tmp_path / "report.json"
        runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        data = json.loads(report_file.read_text())
        assert isinstance(data["per_card_rates"], dict)

    def test_report_has_additional_summary_fields(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """Report should also contain divergence_rate, games_completed_without_divergence, top_divergence_causes."""
        report_file = tmp_path / "report.json"
        runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        data = json.loads(report_file.read_text())
        assert "divergence_rate" in data
        assert "games_completed_without_divergence" in data
        assert "top_divergence_causes" in data

    def test_report_creates_parent_directories(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """--report should create parent dirs if they don't exist."""
        report_file = tmp_path / "subdir" / "nested" / "report.json"
        result = runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        assert result.exit_code == 0
        assert report_file.exists()

    def test_report_output_message(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """Should echo the report path when written."""
        report_file = tmp_path / "report.json"
        result = runner.invoke(
            main, ["validate", sample_replay_path, "--report", str(report_file)]
        )
        assert "Report written to" in result.output


class TestCardsFilter:
    """Tests for --cards filtering option."""

    def test_cards_filter_no_match(
        self, runner: CliRunner
    ) -> None:
        """--cards with a non-existent card name should report no replays found."""
        result = runner.invoke(
            main, ["validate", str(REPLAYS_DIR), "--cards", "Nonexistent Card XYZ"]
        )
        assert result.exit_code == 0
        assert "No replays found" in result.output

    def test_cards_filter_with_matching_card(
        self, runner: CliRunner, sample_replay_path: str, tmp_path: Path
    ) -> None:
        """--cards with a card that exists in the replay should process it."""
        # Mountain (grpId 95197) is in the sample replay
        report_file = tmp_path / "report.json"
        result = runner.invoke(
            main,
            ["validate", str(REPLAYS_DIR), "--cards", "Mountain", "--report", str(report_file)],
        )
        # Should either find the replay and report, or report no match
        # If Mountain is in sample_replay, games_attempted >= 1
        assert result.exit_code == 0


class TestVerboseFlag:
    """Tests for --verbose flag."""

    def test_verbose_shows_validation_details(
        self, runner: CliRunner, sample_replay_path: str
    ) -> None:
        """--verbose should produce more detailed output than non-verbose."""
        quiet_result = runner.invoke(main, ["validate", sample_replay_path])
        verbose_result = runner.invoke(
            main, ["validate", sample_replay_path, "--verbose"]
        )
        assert verbose_result.exit_code == 0
        # Verbose should include the file name being validated
        assert "Validating" in verbose_result.output
        # Verbose output should be longer than non-verbose
        assert len(verbose_result.output) >= len(quiet_result.output)


class TestStopOnDivergence:
    """Tests for --stop-on-divergence flag."""

    def test_stop_on_divergence_message(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """When divergence occurs with --stop-on-divergence, should report stopping."""
        # Create two replay files; mock validate_replay to return divergences
        for i in range(2):
            replay = {
                "seat_id": 1,
                "opponent_seat_id": 2,
                "events": [
                    {
                        "gameStateMessage": {
                            "type": "GameStateType_Full",
                            "gameStateId": 1,
                            "gameObjects": [],
                            "zones": [],
                            "players": [
                                {"systemSeatNumber": 1, "lifeTotal": 20, "maxHandSize": 7},
                                {"systemSeatNumber": 2, "lifeTotal": 20, "maxHandSize": 7},
                            ],
                            "turnInfo": {"turnNumber": 1, "activePlayer": 1, "phase": "Phase_Beginning"},
                        }
                    }
                ],
            }
            (tmp_path / f"replay_{i}.json").write_text(json.dumps(replay))

        from silverquillm.replay.validation import Divergence, DivergenceType, ValidationReport

        div_report = ValidationReport(
            total_snapshots=1,
            successful_comparisons=0,
            divergences=[
                Divergence(
                    game_state_id=1,
                    divergence_type=DivergenceType.STATE_MISMATCH,
                    description="test divergence",
                    involved_grp_ids=[],
                )
            ],
        )

        with patch(
            "silverquillm.replay.cli.validate_replay", return_value=div_report
        ):
            result = runner.invoke(
                main,
                ["validate", str(tmp_path), "--stop-on-divergence"],
            )
        assert result.exit_code == 0
        assert "Stopped" in result.output or "stop" in result.output.lower()

    def test_stop_on_divergence_processes_only_until_first_divergence(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """With --stop-on-divergence, should stop processing after first file with divergence."""
        for i in range(3):
            replay = {
                "seat_id": 1,
                "opponent_seat_id": 2,
                "events": [
                    {
                        "gameStateMessage": {
                            "type": "GameStateType_Full",
                            "gameStateId": 1,
                            "gameObjects": [],
                            "zones": [],
                            "players": [
                                {"systemSeatNumber": 1, "lifeTotal": 20, "maxHandSize": 7},
                                {"systemSeatNumber": 2, "lifeTotal": 20, "maxHandSize": 7},
                            ],
                            "turnInfo": {"turnNumber": 1, "activePlayer": 1, "phase": "Phase_Beginning"},
                        }
                    }
                ],
            }
            (tmp_path / f"replay_{i}.json").write_text(json.dumps(replay))

        from silverquillm.replay.validation import Divergence, DivergenceType, ValidationReport

        div_report = ValidationReport(
            total_snapshots=1,
            successful_comparisons=0,
            divergences=[
                Divergence(
                    game_state_id=1,
                    divergence_type=DivergenceType.STATE_MISMATCH,
                    description="divergence",
                    involved_grp_ids=[],
                )
            ],
        )

        with patch(
            "silverquillm.replay.cli.validate_replay", return_value=div_report
        ):
            result = runner.invoke(
                main,
                ["validate", str(tmp_path), "--stop-on-divergence", "--report", str(tmp_path / "r.json")],
            )
        data = json.loads((tmp_path / "r.json").read_text())
        # Should have stopped after first divergence, so games_attempted should be 1
        assert data["games_attempted"] == 1


class TestSummaryOutput:
    """Tests for summary output format."""

    def test_summary_includes_validation_header(
        self, runner: CliRunner, sample_replay_path: str
    ) -> None:
        """Summary should include a 'Validation Summary' header."""
        result = runner.invoke(main, ["validate", sample_replay_path])
        assert "Validation Summary" in result.output

    def test_summary_includes_games_completed(
        self, runner: CliRunner, sample_replay_path: str
    ) -> None:
        """Summary should report games completed without divergence."""
        result = runner.invoke(main, ["validate", sample_replay_path])
        assert "Games completed without divergence" in result.output


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_path_shows_error(self, runner: CliRunner) -> None:
        """Non-existent path should produce an error."""
        result = runner.invoke(main, ["validate", "/nonexistent/path/to/replay"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_empty_directory_shows_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Empty directory should produce an error about no replay files."""
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0
        assert "no replay" in result.output.lower() or "error" in result.output.lower()

    def test_non_json_file_in_directory(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Directory with only non-JSON files should report no replays."""
        (tmp_path / "readme.txt").write_text("not a replay")
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0

    def test_invalid_json_file_handled_gracefully(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Malformed JSON replay should not crash the CLI."""
        (tmp_path / "bad.json").write_text("{invalid json content")
        result = runner.invoke(main, ["validate", str(tmp_path)])
        # Should either skip or report error, but not crash with traceback
        # Exit code 0 is ok if it reported the error gracefully
        assert result.exit_code == 0 or "error" in result.output.lower()


class TestEndToEnd:
    """End-to-end integration tests with real sample data."""

    @pytest.mark.integration
    def test_e2e_sample_replay_generates_valid_report(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Run against data/replays/ and verify report structure."""
        report_file = tmp_path / "e2e_report.json"
        result = runner.invoke(
            main,
            ["validate", str(SAMPLE_REPLAY), "--report", str(report_file)],
        )
        assert result.exit_code == 0
        assert report_file.exists()

        data = json.loads(report_file.read_text())
        # Required fields per TODO spec
        assert data["games_attempted"] == 1
        assert isinstance(data["divergences"], list)
        assert isinstance(data["per_card_rates"], dict)
        assert isinstance(data["divergence_rate"], (int, float))
        assert isinstance(data["games_completed_without_divergence"], int)
        assert isinstance(data["top_divergence_causes"], list)
        assert isinstance(data["total_divergences"], int)

    @pytest.mark.integration
    def test_e2e_replays_directory_report(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Run against data/replays/ directory and verify report."""
        report_file = tmp_path / "dir_report.json"
        result = runner.invoke(
            main,
            ["validate", str(REPLAYS_DIR), "--report", str(report_file)],
        )
        assert result.exit_code == 0
        data = json.loads(report_file.read_text())
        assert data["games_attempted"] >= 1

    @pytest.mark.integration
    def test_e2e_divergence_entries_have_required_fields(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Each divergence entry in the report should have type, description, game_state_id."""
        report_file = tmp_path / "fields_report.json"
        runner.invoke(
            main,
            ["validate", str(SAMPLE_REPLAY), "--report", str(report_file)],
        )
        data = json.loads(report_file.read_text())
        for div in data["divergences"]:
            assert "type" in div
            assert "description" in div
            assert "game_state_id" in div
            assert "involved_grp_ids" in div
