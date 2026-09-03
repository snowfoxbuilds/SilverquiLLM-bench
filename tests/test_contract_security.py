"""Security properties of the Contract Run driver.

The benchmark process is the trusted, credentialed side of the boundary; the
checkout is candidate-controlled from launch onward.  These tests prove that
nothing candidate-authored ever executes in the benchmark process:

- a candidate-edited ``.theozolith/gate.toml`` command reaches the container
  only as a job over ``input/jobs/`` ↔ ``output/jobs/`` — the driver never
  spawns it (there is no host step runner, statically and dynamically);
- git hooks and config planted in the checkout's ``.git`` never run at the
  driver's post-exit commit (it goes through the driver-owned repository);
- a symlink planted in the checkout is never followed by the harvest.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from silverquillm import contract as contract_mod
from silverquillm import jobdir as jobdir_mod
from silverquillm.contract import drive_contract_run
from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import driver_git_dir, load_benchmark
from silverquillm.modes import get_mode
from silverquillm.proposal import PROPOSAL_APPLIED
from tests.candidate_fixtures import fake_image_builder, make_candidate_dir
from tests.contract_harness import make_rig

PROPOSAL = {
    "pr-title": "Smoke targets",
    "pr-description": "Implements the smoke pool.",
    "commit-message": "Implement Leyline Axe\n\nbody",
}


@pytest.fixture
def fast_eval(monkeypatch):
    def _stub(run_dir, benchmark, timeout=60):
        assert (Path(run_dir) / "workspace_final").is_dir()
        return FullEvalResult()

    monkeypatch.setattr(contract_mod, "evaluate_run", _stub)


def _spy_process_spawns(monkeypatch) -> list[list[str]]:
    """Record every process the benchmark process spawns (``subprocess.run``
    goes through ``Popen``; ``os.system`` is spied too)."""
    spawned: list[list[str]] = []
    real_popen = subprocess.Popen

    class SpyPopen(real_popen):
        def __init__(self, args, *a, **kw):
            spawned.append([str(x) for x in args] if isinstance(args, (list, tuple)) else [str(args)])
            super().__init__(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", SpyPopen)
    import os as _os

    def _no_system(command):
        spawned.append([str(command)])
        raise AssertionError("os.system must never be used by the driver")

    monkeypatch.setattr(_os, "system", _no_system)
    return spawned


@pytest.fixture(scope="module")
def candidate_dir(tmp_path_factory) -> Path:
    """One fixture Candidate Bundle for the module (a real export)."""
    return make_candidate_dir(tmp_path_factory.mktemp("candidate"))


def _drive(tmp_path: Path, rig, *, run_id: str, candidate: Path):
    return drive_contract_run(
        run_dir=tmp_path / "run",
        run_id=run_id,
        benchmark=load_benchmark("smoke"),
        mode=get_mode("basic"),
        budget_seconds=600,
        candidate=candidate,
        session_factory=rig.session_factory,
        image_builder=fake_image_builder,
    )


class TestGateCommandsNeverRunOnTheHost:
    def test_candidate_gate_toml_travels_the_jobs_channel_only(self, tmp_path: Path, monkeypatch, fast_eval, candidate_dir: Path) -> None:
        sentinel = tmp_path / "HOST_EXECUTED"
        command = f"python3 -c \"open({str(sentinel)!r}, 'w').close()\""
        gate_toml = "[steps.test]\nrun = " + json.dumps(command) + "\n"
        recorded: list[dict] = []

        def container_side_runner(cmd: str, cwd: Path, timeout: float) -> tuple[bool, int, str]:
            # The harness's job-execution seam — the container-side shell in
            # production.  Recording instead of executing proves the driver
            # relies on the container for execution: nothing else runs it.
            recorded.append({"command": cmd, "cwd": str(cwd), "timeout": timeout})
            return False, 1, "recorded by the test container; not executed"

        rig = make_rig(
            tmp_path, monkeypatch,
            playbook={
                "implement": ["129"],
                "write_files": {".theozolith/gate.toml": gate_toml},
                "proposal": PROPOSAL,
            },
            job_runner=container_side_runner,
        )
        spawned = _spy_process_spawns(monkeypatch)
        result = _drive(tmp_path, rig, run_id="smoke-sentinel", candidate=candidate_dir)
        job = result.job_dir

        # The sentinel never fired anywhere, and no process the benchmark
        # process spawned carried it.
        assert not sentinel.exists()
        assert all(str(sentinel) not in " ".join(argv) for argv in spawned), spawned
        assert all(command not in " ".join(argv) for argv in spawned), spawned

        # The command travelled the jobs channel exactly once and was handled
        # by the container side alone.
        assert recorded == [{"command": command, "cwd": str(job / "checkout"), "timeout": 900.0}]
        request = json.loads((job / "input" / "jobs" / "001-gate.json").read_text())
        assert request["command"] == command
        answer = json.loads((job / "output" / "jobs" / "001-gate.json").read_text())
        assert answer["ok"] is False and "not executed" in answer["output"]

        # The driver saw the container's answer as a gate finding and carried on.
        assert result.gate.steps_run == ["test"]
        [finding] = [f for f in result.gate.findings if f.severity == "error"]
        assert finding.step == "test" and "not executed" in finding.detail
        assert result.proposal_status == PROPOSAL_APPLIED and result.commit_sha

    def test_driver_has_no_host_step_runner(self) -> None:
        """Statically: no ``shell=True`` anywhere in the driver or staging, no
        ``subprocess_step_runner``, no ``subprocess`` in the driver at all, and
        every process staging spawns is ``git`` with a literal argv."""
        assert not hasattr(contract_mod, "subprocess_step_runner")
        driver_source = inspect.getsource(contract_mod)
        assert "shell=True" not in driver_source
        assert "import subprocess" not in driver_source
        staging_source = inspect.getsource(jobdir_mod)
        assert "shell=True" not in staging_source
        spawns = [
            node
            for node in ast.walk(ast.parse(staging_source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        assert spawns, "expected the staging git calls"
        for call in spawns:
            assert call.func.attr == "run"
            first = call.args[0]
            assert isinstance(first, ast.List), ast.dump(call)
            assert isinstance(first.elts[0], ast.Constant) and first.elts[0].value == "git"


class TestCandidateGitMetadataNeverRunsAtTheDriverCommit:
    def test_planted_hooks_and_config_are_inert(self, tmp_path: Path, monkeypatch, fast_eval, candidate_dir: Path) -> None:
        hook_ran = tmp_path / "HOOK_RAN"
        fsmonitor_ran = tmp_path / "FSMONITOR_RAN"
        rig = make_rig(
            tmp_path, monkeypatch,
            playbook={
                "implement": ["129"],
                "write_files": {
                    ".git/hooks/pre-commit": f"#!/bin/sh\ntouch {hook_ran}\n",
                    ".git/hooks/post-commit": f"#!/bin/sh\ntouch {hook_ran}\n",
                    ".git/hooks/post-index-change": f"#!/bin/sh\ntouch {hook_ran}\n",
                },
                "git_config": {"core.fsmonitor": f"touch {fsmonitor_ran}; false"},
                "proposal": PROPOSAL,
            },
        )
        result = _drive(tmp_path, rig, run_id="smoke-hooks", candidate=candidate_dir)
        assert result.ok, [f.to_dict() for f in result.failures]
        assert result.commit_sha
        assert not hook_ran.exists() and not fsmonitor_ran.exists()
        # The commit landed in the driver-owned repository, with the trailer,
        # and recorded the agent's work.
        driver = driver_git_dir(result.run_dir)
        log = subprocess.run(
            ["git", "--git-dir", str(driver), "log", "-1", "--format=%B"],
            capture_output=True, text=True, check=True,
        ).stdout
        assert "Ozolith-Run: smoke-hooks" in log
        tree = subprocess.run(
            ["git", "--git-dir", str(driver), "ls-tree", "-r", "--name-only", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        assert "cards/fdn/fdn_129/card_impl.py" in tree
        assert not any(name.startswith(".git/") for name in tree)
        # The candidate's own repository is untouched and unharvested.
        assert not (result.run_dir / "workspace_final" / ".git").exists()


class TestTamperedManifestNeverRedirectsTheDriver:
    def test_rewritten_workdir_does_not_move_commit_or_harvest(self, tmp_path: Path, monkeypatch, fast_eval, candidate_dir: Path) -> None:
        """The bind-mounted manifest is agent-writable from launch onward; the
        driver's post-exit steps use the path it *staged*, never a re-read."""
        outside = tmp_path / "outside-workdir"
        outside.mkdir()
        (outside / "planted.txt").write_text("candidate-chosen tree")
        tampered = json.dumps(
            {
                "run_id": "smoke-tamper", "mode": "run", "adapter": "claude",
                "workdir": f"../{outside.name}", "agent_timeout_seconds": 600.0,
                "jobs_idle_timeout_seconds": 600.0, "round": 1, "round_budget": 0,
                "schema_version": 1,
            }
        )
        rig = make_rig(
            tmp_path, monkeypatch,
            playbook={
                "implement": ["129"],
                # The workdir is the checkout, so ../input/ is the job dir's input/.
                "write_files": {"../input/manifest.json": tampered},
                "proposal": PROPOSAL,
            },
        )
        result = _drive(tmp_path, rig, run_id="smoke-tamper", candidate=candidate_dir)
        assert result.ok, [f.to_dict() for f in result.failures]
        final = result.run_dir / "workspace_final"
        assert (final / "cards" / "fdn" / "fdn_129" / "card_impl.py").is_file()
        assert not (final / "planted.txt").exists()
        tree = subprocess.run(
            ["git", "--git-dir", str(driver_git_dir(result.run_dir)), "ls-tree", "-r",
             "--name-only", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        assert "cards/fdn/fdn_129/card_impl.py" in tree and "planted.txt" not in tree


class TestHarvestNeverFollowsCandidateSymlinks:
    def test_symlink_out_of_the_checkout_is_skipped(self, tmp_path: Path, monkeypatch, fast_eval, candidate_dir: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("host file")
        rig = make_rig(
            tmp_path, monkeypatch,
            playbook={
                "symlinks": {"cards/fdn/leak": str(outside), "leak.txt": str(outside / "secret.txt")},
                "proposal": PROPOSAL,
            },
        )
        result = _drive(tmp_path, rig, run_id="smoke-symlink", candidate=candidate_dir)
        final = result.run_dir / "workspace_final"
        assert not (final / "cards" / "fdn" / "leak").exists() and not (final / "cards" / "fdn" / "leak").is_symlink()
        assert not (final / "leak.txt").exists() and not (final / "leak.txt").is_symlink()
        assert not list(final.rglob("secret.txt"))
        assert any("harvest skipped symlinks" in w and "cards/fdn/leak" in w for w in result.warnings)
