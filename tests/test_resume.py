"""Tests for the resume feature.

Covers:
- ``stage_workspace_from_prior_run`` staging variant (workspace.py)
- ``build_resume_preamble`` content / conditional lines
- ``silverquillm resume`` CLI (resolver, --timeout policy, --image
  defaulting + cross-image warning, refuse conditions,
  --force-missing-summary, filter mismatch detection, prompt structure)
- ``silverquillm chain`` reader (oldest-first ordering, cycle detection)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from silverquillm.cli import main
from silverquillm.runner import LifecycleResult
from silverquillm.workspace import (
    build_resume_preamble,
    stage_workspace_from_prior_run,
)


# ---------------------------------------------------------------------------
# Fixtures: build a synthetic "prior run" results dir
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _make_prior_run(
    parent: Path,
    *,
    run_name: str = "sos-prior-2026-05-25T10-00",
    image_dir: str = "pi-blind",
    docker_image: str = "silverquillm-pi-blind:latest",
    timeout_seconds: int = 3600,
    wall_clock_seconds: float = 1800.0,
    run_status: str | None = "completed",
    card_filter: list[str] | None = None,
    include_summary: bool = True,
    include_workspace_final_git: bool = True,
    tracking_files: dict[str, str] | None = None,
    resumed_from: str | None = None,
) -> Path:
    """Build a minimal but realistic prior run directory and return its path.

    The returned path is ``parent/docker/<image_dir>/results/<run_name>/``.
    """
    run_dir = parent / "docker" / image_dir / "results" / run_name
    run_dir.mkdir(parents=True)

    workspace_final = run_dir / "workspace_final"
    workspace_final.mkdir()

    # Minimal workspace contents
    (workspace_final / "prompt.md").write_text(
        "Original User Prompt body.\n", encoding="utf-8"
    )
    (workspace_final / "run_manifest.json").write_text(
        json.dumps(
            {
                "timeout_seconds": timeout_seconds,
                "deadline_utc": "2026-05-25T11:00:00Z",
                "docker_image": docker_image,
                "card_filter": card_filter,
                "benchmark_set": "sos",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Initialize git history so the resume staging guard is satisfied.
    if include_workspace_final_git:
        _git(workspace_final, "init", "-q")
        _git(workspace_final, "add", "-A")
        _git(workspace_final, "commit", "-q", "-m", "prior run seed")
        # Add a second commit so log shows continuity.
        (workspace_final / "RUN_DECISIONS.md").write_text(
            "prior decision 1\n", encoding="utf-8"
        )
        _git(workspace_final, "add", "-A")
        _git(workspace_final, "commit", "-q", "-m", "prior decision")

    # Carry-over tracking files (e.g. coordinator-style)
    if tracking_files:
        for name, body in tracking_files.items():
            (workspace_final / name).write_text(body, encoding="utf-8")
        if include_workspace_final_git:
            _git(workspace_final, "add", "-A")
            _git(workspace_final, "commit", "-q", "-m", "tracking files")

    # Per-run files in the run dir
    manifest = {
        "timeout_seconds": timeout_seconds,
        "deadline_utc": "2026-05-25T11:00:00Z",
        "docker_image": docker_image,
        "card_filter": card_filter,
        "benchmark_set": "sos",
    }
    if resumed_from is not None:
        manifest["resumed_from"] = resumed_from
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if include_summary:
        summary = {
            "docker_image": docker_image,
            "wall_clock_seconds": wall_clock_seconds,
            "card_filter": card_filter,
        }
        if run_status is not None:
            summary["run_status"] = run_status
        if resumed_from is not None:
            summary["resumed_from"] = resumed_from
        (run_dir / "run_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )

    return run_dir


# ---------------------------------------------------------------------------
# stage_workspace_from_prior_run
# ---------------------------------------------------------------------------


class TestStageWorkspaceFromPriorRun:
    def test_preserves_git_directory(self, tmp_path):
        prior = _make_prior_run(tmp_path)
        staging = tmp_path / "stage1"
        staging.mkdir()
        ws, _ = stage_workspace_from_prior_run(
            staging,
            prior,
            prompt_text="resumed prompt",
            run_manifest={"timeout_seconds": 600, "docker_image": "i"},
        )
        assert (ws / ".git").is_dir()
        # And the prior commit history is reachable
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=ws, capture_output=True, text=True
        )
        assert log.returncode == 0
        assert "prior run seed" in log.stdout
        assert "prior decision" in log.stdout

    def test_preserves_tracking_files(self, tmp_path):
        prior = _make_prior_run(
            tmp_path,
            tracking_files={
                "KEY_DECISIONS.md": "decisions\n",
                "MODEL_AUDIT.jsonl": '{"k":1}\n',
                "FILES_MODIFIED.json": '{"cycles":[]}',
                "RUN_DECISIONS.md": "first\n",
            },
        )
        staging = tmp_path / "stage1"
        staging.mkdir()
        ws, _ = stage_workspace_from_prior_run(
            staging,
            prior,
            prompt_text="resumed prompt",
            run_manifest={"timeout_seconds": 600},
        )
        for name in (
            "KEY_DECISIONS.md",
            "MODEL_AUDIT.jsonl",
            "FILES_MODIFIED.json",
            "RUN_DECISIONS.md",
        ):
            assert (ws / name).is_file(), f"{name} should carry over"

    def test_overwrites_prompt_and_manifest(self, tmp_path):
        prior = _make_prior_run(tmp_path)
        staging = tmp_path / "stage1"
        staging.mkdir()
        manifest = {"timeout_seconds": 1234, "deadline_utc": "x"}
        ws, _ = stage_workspace_from_prior_run(
            staging,
            prior,
            prompt_text="NEW prompt content",
            run_manifest=manifest,
        )
        assert (ws / "prompt.md").read_text() == "NEW prompt content"
        assert json.loads((ws / "run_manifest.json").read_text()) == manifest

    def test_raises_when_workspace_final_missing(self, tmp_path):
        prior = tmp_path / "fakerun"
        prior.mkdir()
        staging = tmp_path / "stage1"
        staging.mkdir()
        with pytest.raises(FileNotFoundError, match="workspace_final"):
            stage_workspace_from_prior_run(
                staging,
                prior,
                prompt_text="x",
                run_manifest={},
            )

    def test_raises_when_git_history_missing(self, tmp_path):
        prior = _make_prior_run(
            tmp_path, include_workspace_final_git=False
        )
        staging = tmp_path / "stage1"
        staging.mkdir()
        with pytest.raises(FileNotFoundError, match=".git history"):
            stage_workspace_from_prior_run(
                staging,
                prior,
                prompt_text="x",
                run_manifest={},
            )

    def test_returns_workspace_and_output(self, tmp_path):
        prior = _make_prior_run(tmp_path)
        staging = tmp_path / "stage1"
        staging.mkdir()
        ws, out = stage_workspace_from_prior_run(
            staging,
            prior,
            prompt_text="x",
            run_manifest={},
        )
        assert ws.name == "workspace"
        assert out.name == "output"
        assert ws.is_dir() and out.is_dir()


# ---------------------------------------------------------------------------
# build_resume_preamble
# ---------------------------------------------------------------------------


class TestBuildResumePreamble:
    def test_always_includes_header_and_base_lines(self):
        out = build_resume_preamble("prior-xyz")
        assert out.startswith("## Resume context")
        assert "prior-xyz" in out
        assert ".git" in out  # mentions git history inspection

    def test_omits_conditional_lines_by_default(self):
        out = build_resume_preamble("prior-xyz")
        assert "Snapshot fallback" not in out
        assert "cross-image" not in out.lower() and "different image" not in out
        assert "card filter" not in out.lower()
        assert "missing or unreadable" not in out

    def test_snapshot_fallback_line(self):
        out = build_resume_preamble(
            "prior-xyz",
            snapshot_fallback_used=True,
            snapshot_utc="2026-05-25T09:42:00Z",
        )
        assert "Snapshot fallback was used" in out
        assert "2026-05-25T09:42:00Z" in out

    def test_image_change_line(self):
        out = build_resume_preamble(
            "prior-xyz",
            image_changed=True,
            prior_image="silverquillm-pi-blind:latest",
            new_image="silverquillm-claude-tested:latest",
        )
        assert "silverquillm-pi-blind:latest" in out
        assert "silverquillm-claude-tested:latest" in out

    def test_filter_mismatch_line(self):
        out = build_resume_preamble(
            "prior-xyz",
            filter_mismatch=True,
            prior_card_filter=["1", "2"],
            new_card_filter=["3"],
        )
        assert "1,2" in out
        assert "3" in out
        assert "inherited" in out.lower()

    def test_missing_summary_line(self):
        out = build_resume_preamble("prior-xyz", missing_summary=True)
        assert "missing or unreadable" in out


# ---------------------------------------------------------------------------
# CLI resolver: prior-run-id (path-or-id) lookup
# ---------------------------------------------------------------------------


class TestResolvePriorRun:
    def test_resolves_bare_id_unique_match(self, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path, run_name="sos-uniq-A")
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)
        resolved = cli_mod._resolve_prior_run("sos-uniq-A")
        assert resolved.resolve() == prior.resolve()

    def test_errors_on_zero_matches(self, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)
        with pytest.raises(Exception, match="No prior run found"):
            cli_mod._resolve_prior_run("does-not-exist")

    def test_errors_on_ambiguous_match(self, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        _make_prior_run(tmp_path, run_name="dup", image_dir="img-a")
        _make_prior_run(tmp_path, run_name="dup", image_dir="img-b")
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)
        with pytest.raises(Exception, match="Ambiguous"):
            cli_mod._resolve_prior_run("dup")

    def test_accepts_full_path(self, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path, run_name="sos-pathy")
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)
        resolved = cli_mod._resolve_prior_run(str(prior))
        assert resolved.resolve() == prior.resolve()


# ---------------------------------------------------------------------------
# CLI: silverquillm resume
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def _patch_resume_deps(monkeypatch):
    """Mock heavy deps so resume can complete in a unit test."""
    with patch("silverquillm.cli.ContainerLifecycle") as cls, \
         patch("silverquillm.cli.build_card_name_map", return_value={}), \
         patch("silverquillm.cli._harvest_results") as harvest, \
         patch("silverquillm.cli._evaluate_results"), \
         patch("silverquillm.cli._generate_run_summary"):
        cls.return_value = MagicMock()
        cls.return_value.run.return_value = LifecycleResult(
            exit_code=0,
            timed_out=False,
            timeout_reason=None,
            container_name="test",
        )
        # Harvest just creates the run dir
        def _harv(workspace, output, results_dir, run_name, **kw):
            d = results_dir / run_name
            d.mkdir(parents=True, exist_ok=True)
            return d
        harvest.side_effect = _harv
        yield cls


class TestResumeCommand:
    def test_requires_timeout(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path)
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(main, ["resume", prior.name])
        assert result.exit_code != 0
        assert "--timeout is required" in result.output
        # Hint should reference prior timeout and wall-clock
        assert "3600s" in result.output
        assert "1800s" in result.output

    def test_refuses_no_viable_output(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(
            tmp_path, run_status="no_viable_output_produced"
        )
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(
            main, ["resume", prior.name, "--timeout", "60"]
        )
        assert result.exit_code != 0
        assert "no_viable_output_produced" in result.output

    def test_refuses_missing_workspace_final(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path)
        # Remove workspace_final after the fact
        import shutil

        shutil.rmtree(prior / "workspace_final")
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(
            main, ["resume", prior.name, "--timeout", "60"]
        )
        assert result.exit_code != 0
        assert "workspace_final" in result.output

    def test_missing_summary_requires_force_flag(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path, include_summary=False)
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(
            main, ["resume", prior.name, "--timeout", "60"]
        )
        assert result.exit_code != 0
        assert "force-missing-summary" in result.output

    def test_refuses_missing_manifest(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path)
        (prior / "run_manifest.json").unlink()
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(
            main, ["resume", prior.name, "--timeout", "60"]
        )
        assert result.exit_code != 0
        assert "run_manifest.json" in result.output

    def test_e2e_resume_writes_manifest_and_preamble(
        self, runner, tmp_path, monkeypatch, _patch_resume_deps
    ):
        from silverquillm import cli as cli_mod
        import shutil as _shutil

        prior = _make_prior_run(tmp_path)
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        snap_dir = tmp_path / "snap"

        def _capture(*args, **kwargs):
            ws = kwargs["workspace"]
            # Snapshot the staged workspace before the run cleans it up.
            _shutil.copytree(ws, snap_dir)
            m = MagicMock()
            m.run.return_value = LifecycleResult(0, False, None, "x")
            return m
        _patch_resume_deps.side_effect = _capture

        result = runner.invoke(
            main, ["resume", prior.name, "--timeout", "60"]
        )
        assert result.exit_code == 0, result.output

        ws = snap_dir
        assert (ws / ".git").is_dir()
        new_manifest = json.loads((ws / "run_manifest.json").read_text())
        assert new_manifest["timeout_seconds"] == 60
        assert new_manifest["resumed_from"] == prior.name
        assert new_manifest["docker_image"] == "silverquillm-pi-blind:latest"
        prompt = (ws / "prompt.md").read_text()
        assert prompt.startswith("## Resume context")
        assert prior.name in prompt
        assert "\n---\n" in prompt
        assert "Original User Prompt body." in prompt

    def test_cross_image_warning_and_marker(
        self, runner, tmp_path, monkeypatch, _patch_resume_deps
    ):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path)
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        captured_kwargs = {}
        original_gen = cli_mod._generate_run_summary
        def _capture_gen(*args, **kwargs):
            captured_kwargs.update(kwargs)
        monkeypatch.setattr(cli_mod, "_generate_run_summary", _capture_gen)

        staged = {}
        def _capture_lc(*args, **kwargs):
            staged["ws"] = kwargs["workspace"]
            m = MagicMock()
            m.run.return_value = LifecycleResult(0, False, None, "x")
            return m
        _patch_resume_deps.side_effect = _capture_lc

        result = runner.invoke(
            main,
            [
                "resume",
                prior.name,
                "--timeout",
                "60",
                "--image",
                "silverquillm-claude-tested:latest",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "cross-image resume" in result.output
        assert captured_kwargs.get("resumed_image_changed") is True
        # The new run dir lands under the NEW image's <image-dir>
        new_image_dir = tmp_path / "docker" / "claude-tested" / "results"
        assert new_image_dir.is_dir()

    def test_filter_mismatch_appears_in_preamble(
        self, runner, tmp_path, monkeypatch, _patch_resume_deps
    ):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path, card_filter=["1", "2"])
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        captured_prompt = {}
        def _capture(*args, **kwargs):
            ws = kwargs["workspace"]
            captured_prompt["text"] = (ws / "prompt.md").read_text()
            m = MagicMock()
            m.run.return_value = LifecycleResult(0, False, None, "x")
            return m
        _patch_resume_deps.side_effect = _capture

        result = runner.invoke(
            main,
            ["resume", prior.name, "--timeout", "60", "--cards", "3"],
        )
        assert result.exit_code == 0, result.output
        prompt = captured_prompt["text"]
        assert "1,2" in prompt
        assert "3" in prompt

    def test_strip_prior_preamble_avoids_nesting(
        self, runner, tmp_path, monkeypatch, _patch_resume_deps
    ):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path)
        # Inject a preamble into the prior workspace's prompt to simulate
        # a leg of a leg.
        prior_prompt = prior / "workspace_final" / "prompt.md"
        prior_prompt.write_text(
            "## Resume context\n\n"
            "This is a Resume Leg of prior Benchmark Run `older-leg`.\n"
            "Inspect `.git` etc.\n"
            "---\n\n"
            "Original User Prompt body.\n",
            encoding="utf-8",
        )
        # Re-commit so workspace_final's git is consistent
        _git(prior / "workspace_final", "add", "-A")
        _git(prior / "workspace_final", "commit", "-q", "-m", "inject preamble")
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        captured = {}
        def _capture(*args, **kwargs):
            captured["text"] = (kwargs["workspace"] / "prompt.md").read_text()
            m = MagicMock()
            m.run.return_value = LifecycleResult(0, False, None, "x")
            return m
        _patch_resume_deps.side_effect = _capture

        result = runner.invoke(
            main, ["resume", prior.name, "--timeout", "60"]
        )
        assert result.exit_code == 0, result.output
        prompt = captured["text"]
        assert prompt.count("## Resume context") == 1
        assert prior.name in prompt
        assert "older-leg" not in prompt


# ---------------------------------------------------------------------------
# CLI: silverquillm chain
# ---------------------------------------------------------------------------


class TestChainCommand:
    def test_single_leg_chain(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        prior = _make_prior_run(tmp_path, run_name="leg-only")
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(main, ["chain", "leg-only"])
        assert result.exit_code == 0, result.output
        assert "leg-only" in result.output
        assert "docker_image" in result.output

    def test_multi_leg_chain_oldest_first(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        leg1 = _make_prior_run(tmp_path, run_name="leg-1")
        leg2 = _make_prior_run(
            tmp_path, run_name="leg-2", resumed_from="leg-1"
        )
        leg3 = _make_prior_run(
            tmp_path, run_name="leg-3", resumed_from="leg-2"
        )
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(main, ["chain", "leg-3"])
        assert result.exit_code == 0, result.output
        # Oldest first ordering
        i1 = result.output.find("leg-1")
        i2 = result.output.find("leg-2")
        i3 = result.output.find("leg-3")
        assert 0 <= i1 < i2 < i3, result.output

    def test_chain_cycle_detection(self, runner, tmp_path, monkeypatch):
        from silverquillm import cli as cli_mod

        # Two legs that point at each other -> cycle
        _make_prior_run(tmp_path, run_name="leg-a", resumed_from="leg-b")
        _make_prior_run(tmp_path, run_name="leg-b", resumed_from="leg-a")
        monkeypatch.setattr(cli_mod, "_REPO_ROOT", tmp_path)

        result = runner.invoke(main, ["chain", "leg-a"])
        assert result.exit_code != 0
        assert "cycle" in result.output.lower()
