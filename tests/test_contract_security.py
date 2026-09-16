"""Candidate-controlled gate, git metadata and symlinks never cross host authority."""

import json
from pathlib import Path

from silverquillm import contract
from silverquillm.evaluator import FullEvalResult
from silverquillm.modes import get_mode
from tests.test_standalone_run import Engine, benchmark, definition


class MutatingEngine(Engine):
    def __init__(self, mutate):
        super().__init__()
        self.mutate = mutate

    def request(self, method, path, body=None, **kwargs):
        result = super().request(method, path, body, **kwargs)
        if path.endswith("/start"):
            row = self.containers[path.split("/")[2]]
            if row["Config"]["Labels"]["silverquillm.construct.role"] == "workload":
                sources = {
                    m["Target"]: Path(m["Source"]) for m in row["Config"]["HostConfig"]["Mounts"]
                }
                self.mutate(sources)
        return result


def execute(tmp_path, monkeypatch, mutate):
    monkeypatch.setattr(contract, "evaluate_run", lambda *a, **kw: FullEvalResult())
    engine = MutatingEngine(mutate)
    result = contract.drive_contract_run(
        run_dir=tmp_path / "run",
        run_id="run",
        candidate=definition(tmp_path),
        benchmark=benchmark(tmp_path),
        mode=get_mode("basic"),
        budget_seconds=5,
        engine=engine,
    )
    return result, engine


def test_candidate_authored_gate_command_only_reaches_isolated_container(tmp_path, monkeypatch):
    marker = tmp_path / "host-must-not-run"
    command = "touch " + str(marker)

    def mutate(sources):
        (sources["/work"] / ".theozolith/gate.toml").write_text(
            "[steps.test]\nrun=" + json.dumps(command) + "\n"
        )

    result, engine = execute(tmp_path, monkeypatch, mutate)
    assert result.ok, result.evidence()
    assert not marker.exists()
    creates = [body for _, path, body in engine.calls if path.startswith("/containers/create")]
    assert creates[-1]["Cmd"] == ["-lc", command]
    assert creates[-1]["Entrypoint"] == ["/bin/sh"]
    assert all(
        "driver.git" not in mount["Source"]
        for body in creates
        for mount in body["HostConfig"]["Mounts"]
    )


def test_candidate_git_hooks_filters_and_configuration_are_inert(tmp_path, monkeypatch):
    marker = tmp_path / "git-must-not-run"

    def mutate(sources):
        root = sources["/work"]
        hook = root / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\ntouch " + str(marker) + "\n")
        hook.chmod(0o755)
        with (root / ".git/config").open("a") as output:
            output.write(
                '\n[core]\n fsmonitor = "touch '
                + str(marker)
                + '"\n[filter "hostile"]\n clean = "touch '
                + str(marker)
                + '"\n required = true\n'
            )
        (root / ".gitattributes").write_text("*.py filter=hostile\n")

    result, _ = execute(tmp_path, monkeypatch, mutate)
    assert result.ok, result.evidence()
    assert not marker.exists()
    assert result.commit_sha
    assert (result.run_dir / "workspace_final/answer.py").is_file()


def test_candidate_metadata_does_not_redirect_commit_or_harvest(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("private host content")

    def mutate(sources):
        (sources["/in"] / "benchmark.json").write_text(json.dumps({"workdir": str(outside)}))
        (sources["/work"] / "escape").symlink_to(outside, target_is_directory=True)
        (sources["/work"] / "file-escape").symlink_to(outside / "secret.txt")

    result, _ = execute(tmp_path, monkeypatch, mutate)
    assert result.ok, result.evidence()
    final = result.run_dir / "workspace_final"
    assert (final / "answer.py").is_file()
    assert not (final / "escape").exists() and not (final / "file-escape").exists()
    assert (outside / "secret.txt").read_text() == "private host content"
    assert any("symlinks" in warning for warning in result.warnings)
