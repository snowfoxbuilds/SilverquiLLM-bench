"""The legacy harvest and its consumers never dereference an agent's links on the host."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from silverquillm.cli import _harvest_results
from silverquillm.evaluator import _prepare_engine_work
from silverquillm.workspace import stage_workspace_from_prior_run

SECRET = "host-only-secret-7f3a"


def host_secret(tmp_path: Path) -> tuple[Path, Path]:
    directory = tmp_path / "host"
    directory.mkdir()
    (directory / "id_rsa").write_text(SECRET)
    (directory / "card_impl.py").write_text(SECRET)
    return directory / "id_rsa", directory


def regular_file_contents(root: Path) -> str:
    text = []
    for directory, names, files in os.walk(root, followlinks=False):
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                text.append(path.read_text(errors="replace"))
    return "\n".join(text)


def hostile_workspace(tmp_path: Path) -> tuple[Path, Path]:
    secret, secret_dir = host_secret(tmp_path)
    workspace = tmp_path / "ws" / "workspace"
    output = tmp_path / "ws" / "output"
    output.mkdir(parents=True)
    (workspace / "cards/sos/sos_1").mkdir(parents=True)
    (workspace / "cards/sos/sos_1/card_impl.py").symlink_to(secret)
    (workspace / "cards/sos/sos_1/tests.py").write_text("def test_ok(): pass\n")
    (workspace / "cards/sos/sos_53").symlink_to(secret_dir)
    (workspace / "engine").mkdir()
    (workspace / "engine/leak.py").symlink_to(secret)
    (workspace / "engine/x").symlink_to(secret_dir)
    (workspace / "run_manifest.json").symlink_to(secret)
    (output / "agent.log").symlink_to(secret)
    return workspace, output


def test_harvest_keeps_links_as_links_and_copies_no_host_file(tmp_path):
    workspace, output = hostile_workspace(tmp_path)
    run_dir = _harvest_results(workspace, output, tmp_path / "results", "run")
    assert SECRET not in regular_file_contents(run_dir)
    assert (run_dir / "cards/sos_1/tests.py").is_file()
    assert not (run_dir / "cards/sos_1/card_impl.py").exists()
    assert not (run_dir / "cards/sos_53/card_impl.py").exists()
    assert not (run_dir / "agent.log").exists()
    assert not (run_dir / "run_manifest.json").exists()
    assert (run_dir / "workspace_final/engine/leak.py").is_symlink()
    assert (run_dir / "workspace_final/engine/x").is_symlink()
    patch = run_dir / "engine_diff.patch"
    assert not patch.exists() or SECRET not in patch.read_text()


def test_engine_staging_for_grading_does_not_dereference_links(tmp_path):
    secret, _ = host_secret(tmp_path)
    engine = tmp_path / "run/workspace_final/engine"
    engine.mkdir(parents=True)
    (engine / "card.py").write_text("value = 1\n")
    (engine / "leak.py").symlink_to(secret)
    staged, staging = _prepare_engine_work(tmp_path / "run", tmp_path / "unused")
    try:
        assert (staged / "leak.py").is_symlink()
        assert SECRET not in regular_file_contents(staging)
    finally:
        shutil.rmtree(staging)


def test_resume_staging_does_not_dereference_a_prior_legs_links(tmp_path):
    secret, _ = host_secret(tmp_path)
    prior = tmp_path / "prior"
    final = prior / "workspace_final"
    (final / ".git").mkdir(parents=True)
    (final / "engine").mkdir()
    (final / "engine/leak.py").symlink_to(secret)
    workspace, _ = stage_workspace_from_prior_run(
        tmp_path / "leg2", prior, prompt_text="resume", run_manifest={"leg": 2}
    )
    assert (workspace / "engine/leak.py").is_symlink()
    assert SECRET not in regular_file_contents(workspace)
    assert json.loads((workspace / "run_manifest.json").read_text()) == {"leg": 2}
