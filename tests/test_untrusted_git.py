"""Host-side git over a candidate's repository never runs what the candidate configured."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from silverquillm import untrusted_git
from silverquillm.cli import _make_snapshot_callback


def committed_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "cards/sos/sos_001").mkdir(parents=True)
    (workspace / "cards/sos/sos_001/card_impl.py").write_text("pass\n")
    (workspace / "engine").mkdir()
    (workspace / "engine/card.py").write_text("# baseline\n")
    for arguments in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "baseline"],
    ):
        subprocess.run(["git", *arguments], cwd=workspace, check=True)
    return workspace


def plant_hostile_config(workspace: Path, marker: Path) -> None:
    """What an agent could leave behind: config that makes git run its program."""
    program = workspace.parent / "planted.sh"
    program.write_text(f"#!/bin/sh\necho ran >> {marker}\n")
    program.chmod(0o755)
    with (workspace / ".git/config").open("a") as config:
        config.write(
            f"[core]\n\tfsmonitor = {program}\n\thooksPath = {workspace.parent}\n"
            f'[filter "planted"]\n\tclean = {program}\n\tsmudge = {program}\n'
        )
    (workspace / ".gitattributes").write_text("* filter=planted\n")


def test_candidate_git_config_is_honored_by_plain_git(tmp_path):
    """Guards the fixture: without isolation, the planted program does run."""
    workspace = committed_workspace(tmp_path)
    marker = tmp_path / "marker"
    plant_hostile_config(workspace, marker)
    subprocess.run(["git", "status"], cwd=workspace, capture_output=True, check=False)
    assert marker.exists()


def test_status_never_runs_a_program_the_candidate_configured(tmp_path):
    workspace = committed_workspace(tmp_path)
    marker = tmp_path / "marker"
    plant_hostile_config(workspace, marker)
    (workspace / "engine/card.py").write_text("# changed\n")
    (workspace / "cards/sos/sos_001/new.py").write_text("x = 1\n")
    paths = untrusted_git.status_paths(workspace)
    assert not marker.exists()
    assert paths is not None
    assert {entry[3:] for entry in paths} >= {"engine/card.py", "cards/sos/sos_001/new.py"}


def test_snapshot_callback_counts_changes_without_running_candidate_programs(tmp_path):
    workspace = committed_workspace(tmp_path)
    marker = tmp_path / "marker"
    plant_hostile_config(workspace, marker)
    (workspace / "engine/card.py").write_text("# changed\n")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _make_snapshot_callback(workspace, run_dir)()
    assert not marker.exists()
    [record] = [json.loads(line) for line in (run_dir / "snapshot_telemetry.jsonl").open()]
    assert record["files_changed"] == 1


def test_symlinked_git_metadata_is_refused_not_followed(tmp_path):
    workspace = committed_workspace(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    os.rename(workspace / ".git/refs", elsewhere)
    (workspace / ".git/refs").symlink_to(elsewhere)
    assert untrusted_git.status_paths(workspace) is None
    (workspace / ".git/refs").unlink()
    os.rename(elsewhere, workspace / ".git/refs")
    os.rename(workspace / ".git", elsewhere)
    (workspace / ".git").symlink_to(elsewhere)
    assert untrusted_git.status_paths(workspace) is None
