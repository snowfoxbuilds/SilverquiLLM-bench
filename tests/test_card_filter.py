"""Tests for --cards filter: workspace staging with card_filter and CLI integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.workspace import stage_workspace


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def fake_cards_dir(tmp_path: Path) -> Path:
    """Create a minimal cards/ tree with FDN and SOS cards for testing."""
    cards = tmp_path / "cards"

    # FDN cards (reference examples — always staged in full)
    fdn = cards / "fdn"
    for cn in ("F1", "F2"):
        d = fdn / cn
        d.mkdir(parents=True)
        (d / "card_spec.json").write_text(
            json.dumps({"name": f"FDN Card {cn}", "collector_number": cn}),
            encoding="utf-8",
        )
        (d / "card_impl.py").write_text(
            f"# Completed FDN implementation for {cn}\n", encoding="utf-8"
        )

    # SOS cards (benchmark targets — subject to filtering)
    sos = cards / "sos"
    for cn in ("001", "042", "105", "200"):
        d = sos / cn
        d.mkdir(parents=True)
        (d / "card_spec.json").write_text(
            json.dumps({"name": f"SOS Card {cn}", "collector_number": cn}),
            encoding="utf-8",
        )
        (d / "card_impl.py").write_text(
            f'"""Card {cn}."""\n\nclass Card{cn}:\n    pass\n',
            encoding="utf-8",
        )

    return cards


@pytest.fixture()
def fake_engine_dir(tmp_path: Path) -> Path:
    """Create a minimal engine/ directory."""
    eng = tmp_path / "engine"
    eng.mkdir(parents=True)
    (eng / "card.py").write_text("# card base\n", encoding="utf-8")
    (eng / "game.py").write_text("# game engine\n", encoding="utf-8")
    return eng


@pytest.fixture()
def fake_docs(tmp_path: Path) -> None:
    """Create stub reference docs so stage_workspace doesn't fail."""
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "engine_api.md").write_text("# Engine API stub\n" * 10, encoding="utf-8")
    (docs / "test_utils.md").write_text("# Test Utils stub\n" * 10, encoding="utf-8")
    (docs / "rulebook.md").write_text("# Rulebook stub\n" * 10, encoding="utf-8")


# ---------------------------------------------------------------------------
# Workspace staging: card_filter parameter
# ---------------------------------------------------------------------------


class TestCardFilterStaging:
    """stage_workspace with card_filter stages only matching SOS cards."""

    def test_filter_stages_only_matching_sos_cards(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """With card_filter=['001', '042'], only those two SOS dirs exist."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=["001", "042"]
        )
        sos = workspace / "cards" / "sos"
        staged = sorted(
            d.name for d in sos.iterdir() if d.is_dir()
        )
        assert staged == ["001", "042"]

    def test_filter_none_stages_all_sos_cards(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """card_filter=None (default) stages every SOS card."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=None
        )
        sos = workspace / "cards" / "sos"
        staged = sorted(
            d.name for d in sos.iterdir() if d.is_dir()
        )
        assert staged == ["001", "042", "105", "200"]

    def test_filter_does_not_affect_fdn_cards(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """FDN cards are always staged in full, even with a restrictive filter."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=["001"]
        )
        fdn = workspace / "cards" / "fdn"
        staged = sorted(
            d.name for d in fdn.iterdir() if d.is_dir()
        )
        assert staged == ["F1", "F2"]

    def test_filter_single_card(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """A single-element filter stages exactly one SOS card."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=["105"]
        )
        sos = workspace / "cards" / "sos"
        staged = [d.name for d in sos.iterdir() if d.is_dir()]
        assert staged == ["105"]

    def test_filter_nonexistent_collector_numbers_stages_nothing(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """Filter with no matching collector numbers stages zero SOS cards."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=["999", "888"]
        )
        sos = workspace / "cards" / "sos"
        staged = [d.name for d in sos.iterdir() if d.is_dir()]
        assert staged == []

    def test_empty_filter_list_stages_no_sos_cards(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """An empty list [] is not None — it means 'stage zero SOS cards'."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=[]
        )
        sos = workspace / "cards" / "sos"
        staged = [d.name for d in sos.iterdir() if d.is_dir()]
        assert staged == []

    def test_staged_card_has_spec_and_impl(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """Filtered cards still get both card_spec.json and card_impl.py."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=["042"]
        )
        card_dir = workspace / "cards" / "sos" / "042"
        assert (card_dir / "card_spec.json").is_file()
        assert (card_dir / "card_impl.py").is_file()


# ---------------------------------------------------------------------------
# Prompt content reflects filter
# ---------------------------------------------------------------------------


class TestPromptContent:
    """prompt.md should mention the subset when card_filter is used."""

    def test_prompt_mentions_all_when_no_filter(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """Default (None): prompt says 'Implement all SOS cards'."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=None
        )
        text = (workspace / "prompt.md").read_text()
        assert "all SOS cards" in text.lower() or "Implement all SOS cards" in text

    def test_prompt_lists_subset_when_filtered(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """With filter: prompt lists specific collector numbers."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=["001", "042"]
        )
        text = (workspace / "prompt.md").read_text()
        assert "001" in text
        assert "042" in text
        # Should NOT say "all SOS cards"
        assert "all SOS cards" not in text.lower()

    def test_prompt_mentions_following_when_filtered(
        self, fake_cards_dir, fake_engine_dir, fake_docs, tmp_path
    ):
        """Filtered prompt uses 'the following SOS cards' phrasing."""
        out = tmp_path / "out"
        out.mkdir()
        workspace, _ = stage_workspace(
            fake_cards_dir, fake_engine_dir, out, card_filter=["105"]
        )
        text = (workspace / "prompt.md").read_text()
        assert "following SOS cards" in text


# ---------------------------------------------------------------------------
# CLI --cards option parsing
# ---------------------------------------------------------------------------


class TestCLICardsOption:
    """The run command should accept --cards and pass it to stage_workspace."""

    def test_run_help_shows_cards_option(self, runner):
        """--cards should appear in run --help output."""
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "--cards" in result.output

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_cards_option_passes_filter_to_stage_workspace(
        self, mock_stage, mock_subprocess, runner, tmp_path
    ):
        """--cards 001,042 should call stage_workspace with card_filter=['001', '042']."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards", "001,042"],
        )

        _, kwargs = mock_stage.call_args
        # card_filter could be a positional or keyword arg
        if "card_filter" in kwargs:
            assert kwargs["card_filter"] == ["001", "042"]
        else:
            # 4th positional arg (cards_dir, engine_dir, output_dir, card_filter)
            args = mock_stage.call_args[0]
            assert args[3] == ["001", "042"]

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_no_cards_option_passes_none(
        self, mock_stage, mock_subprocess, runner, tmp_path
    ):
        """Omitting --cards should pass card_filter=None."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img"])

        _, kwargs = mock_stage.call_args
        if "card_filter" in kwargs:
            assert kwargs["card_filter"] is None
        else:
            args = mock_stage.call_args[0]
            # When omitted, should not pass card_filter or pass None
            assert len(args) <= 3 or args[3] is None

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_cards_with_spaces_are_stripped(
        self, mock_stage, mock_subprocess, runner, tmp_path
    ):
        """--cards '001, 042 , 105' should strip whitespace from each number."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards", "001, 042 , 105"],
        )

        _, kwargs = mock_stage.call_args
        if "card_filter" in kwargs:
            filt = kwargs["card_filter"]
        else:
            filt = mock_stage.call_args[0][3]
        assert filt == ["001", "042", "105"]

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_cards_filter_echoed_in_output(
        self, mock_stage, mock_subprocess, runner, tmp_path
    ):
        """When --cards is used, the CLI should echo the filter."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = runner.invoke(
            main,
            ["run", "--image", "test-img", "--cards", "001,042"],
        )

        assert "001" in result.output
        assert "042" in result.output


# ---------------------------------------------------------------------------
# CLI default directories
# ---------------------------------------------------------------------------


class TestCLIDefaults:
    """--cards-dir and --engine-dir should have sensible defaults."""

    def test_run_help_shows_cards_dir_default(self, runner):
        result = runner.invoke(main, ["run", "--help"])
        assert "--cards-dir" in result.output

    def test_run_help_shows_engine_dir_default(self, runner):
        result = runner.invoke(main, ["run", "--help"])
        assert "--engine-dir" in result.output

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_run_default_cards_dir_resolves_to_repo_root(
        self, mock_stage, mock_subprocess, runner, tmp_path
    ):
        """When --cards-dir is omitted, stage_workspace receives repo_root/cards."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img"])

        from silverquillm.cli import _REPO_ROOT

        args, kwargs = mock_stage.call_args
        cards_dir_arg = args[0] if args else kwargs.get("cards_dir")
        assert cards_dir_arg == _REPO_ROOT / "cards"

    @patch("silverquillm.cli.subprocess.run")
    @patch("silverquillm.cli.stage_workspace")
    def test_run_default_engine_dir_resolves_to_repo_root(
        self, mock_stage, mock_subprocess, runner, tmp_path
    ):
        """When --engine-dir is omitted, stage_workspace receives repo_root/engine."""
        workspace = tmp_path / "workspace"
        output = tmp_path / "output"
        workspace.mkdir()
        output.mkdir()
        mock_stage.return_value = (workspace, output)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner.invoke(main, ["run", "--image", "test-img"])

        from silverquillm.cli import _REPO_ROOT

        args, kwargs = mock_stage.call_args
        engine_dir_arg = args[1] if len(args) > 1 else kwargs.get("engine_dir")
        assert engine_dir_arg == _REPO_ROOT / "engine"


# ---------------------------------------------------------------------------
# smoke command: --cards-dir and --engine-dir support
# ---------------------------------------------------------------------------


class TestSmokeCommandOptions:
    """The smoke command should also accept --cards-dir and --engine-dir."""

    def test_smoke_help_shows_cards_dir(self, runner):
        """smoke --help should list --cards-dir."""
        result = runner.invoke(main, ["smoke", "--help"])
        assert result.exit_code == 0
        assert "--cards-dir" in result.output

    def test_smoke_help_shows_engine_dir(self, runner):
        """smoke --help should list --engine-dir."""
        result = runner.invoke(main, ["smoke", "--help"])
        assert result.exit_code == 0
        assert "--engine-dir" in result.output


# ---------------------------------------------------------------------------
# run_summary.json records card_filter
# ---------------------------------------------------------------------------


class TestRunSummaryCardFilter:
    """_generate_run_summary should record card_filter in run_metadata."""

    def test_card_filter_recorded_when_set(self, tmp_path):
        """card_filter list is written to run_summary.json.run_metadata."""
        from silverquillm.cli import _generate_run_summary

        run_dir = tmp_path / "run_abc"
        run_dir.mkdir()

        _generate_run_summary(run_dir, card_filter=["001", "042", "105"])

        summary = json.loads((run_dir / "run_summary.json").read_text())
        assert summary["run_metadata"]["card_filter"] == ["001", "042", "105"]

    def test_card_filter_null_when_omitted(self, tmp_path):
        """card_filter is null when no filter was applied."""
        from silverquillm.cli import _generate_run_summary

        run_dir = tmp_path / "run_full"
        run_dir.mkdir()

        _generate_run_summary(run_dir, card_filter=None)

        summary = json.loads((run_dir / "run_summary.json").read_text())
        assert summary["run_metadata"]["card_filter"] is None

    def test_card_filter_default_is_none(self, tmp_path):
        """Calling without card_filter kwarg defaults to None."""
        from silverquillm.cli import _generate_run_summary

        run_dir = tmp_path / "run_default"
        run_dir.mkdir()

        _generate_run_summary(run_dir)

        summary = json.loads((run_dir / "run_summary.json").read_text())
        assert summary["run_metadata"]["card_filter"] is None
