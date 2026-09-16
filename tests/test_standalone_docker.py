"""Actual local Docker qualification; synthetic credentials and no vendor services."""

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from karn import bootstrap, initializer
from karn.definition import canonical, new_definition

from silverquillm import contract
from silverquillm.docker_host import DockerEngine
from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import BenchmarkRef
from silverquillm.modes import get_mode

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def fixture_image(tmp_path_factory):
    root = tmp_path_factory.mktemp("standalone-image")
    fixture = Path(__file__).parent / "fixtures/standalone"
    for name in ("Dockerfile", "probe.py"):
        shutil.copyfile(fixture / name, root / name)
    for module, name in ((bootstrap, "bootstrap.py"), (initializer, "initializer.py")):
        shutil.copyfile(module.__file__, root / name)
    result = subprocess.run(
        ["docker", "build", "--iidfile", str(root / "image.id"), str(root)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-8000:]
    image = (root / "image.id").read_text().strip()
    yield image
    subprocess.run(["docker", "image", "rm", image], capture_output=True, timeout=30, check=False)


def candidate(tmp_path, image, *, behavior="valid", sudo=False, variant="one"):
    doc = new_definition(
        name="docker-fixture",
        mode="automaton",
        image=image,
        main=["python3", "/fixture/probe.py"],
        definition_version=3,
    ).document
    runtime = doc["runtime"]
    runtime.update(
        sudo=sudo,
        timeout_seconds=1 if behavior == "timeout" else 30,
        environment={"BENCH_BEHAVIOR": behavior, "BENCH_VARIANT": variant},
        initializer=[
            "python3",
            "-c",
            "from pathlib import Path; Path('/work/initializer.txt').write_text('prepared')",
        ],
        initializer_runner=["python3", "/fixture/initializer.py"],
        bootstrap={
            "argv": ["python3", "/fixture/bootstrap.py"],
            "protocol": "identity-v2",
            "identity_input": "/in/identity.json",
            "handoff": "/out/handoff.json",
            "home": "/home/construct",
            "shell": "/bin/sh",
        },
    )
    runtime["mounts"] = [
        {
            "name": name,
            "target": target,
            "source": {"kind": "runtime", "value": name},
            "purpose": name,
            "persistent": False,
            "access": "read_only" if name == "input" else "read_write",
        }
        for name, target in [("workspace", "/work"), ("input", "/in"), ("output", "/out")]
    ]
    runtime["files"] = [
        {"name": name, "mount": mount, "path": path, "direction": direction, "schema": schema}
        for name, mount, path, direction, schema in [
            ("prompt", "input", "nested/prompt.md", "input", {"type": "string"}),
            ("request", "input", "request.json", "input", {"type": "object"}),
            ("identity", "input", "identity.json", "input", {"type": "object"}),
            ("handoff", "output", "handoff.json", "status", {"type": "object"}),
            ("proposal", "output", "nested/proposal.json", "output", {"type": "object"}),
        ]
    ]
    path = tmp_path / (variant + "-definition.json")
    path.write_bytes(canonical(doc))
    return path


def benchmark(tmp_path):
    root = tmp_path / "benchmark"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "seed.py").write_text("seed=True\n")
    (workspace / ".theozolith").mkdir()
    (workspace / ".theozolith/gate.toml").write_text(
        '[steps.lint]\nrun="python3 -c \'print(1)\'"\n[steps.test]\nrun="test -f initializer.txt"\n[steps.docs]\nrun="test -f fixture-observation.json"\n'
    )
    return BenchmarkRef(
        "fixture",
        root,
        {
            "id": "fixture",
            "draft_set": {"primary_set_code": "FDN"},
            "cards": ["1"],
            "leaderboard": {"eligible": False},
        },
    )


@pytest.mark.parametrize(
    "behavior,sudo",
    [("valid", False), ("valid", True), ("invalid", False), ("failed", False), ("timeout", False)],
)
def test_declared_process_identity_outcomes_and_owned_cleanup(
    tmp_path, monkeypatch, fixture_image, behavior, sudo
):
    monkeypatch.setattr(contract, "evaluate_run", lambda *a, **kw: FullEvalResult())
    path = candidate(tmp_path, fixture_image, behavior=behavior, sudo=sudo)
    run_id = "qualification-" + uuid.uuid4().hex[:10]
    result = contract.drive_contract_run(
        run_dir=tmp_path / run_id,
        run_id=run_id,
        benchmark=benchmark(tmp_path),
        mode=get_mode("basic"),
        budget_seconds=30,
        candidate=path,
        results_repo=tmp_path / "results",
    )
    assert result.ok is (behavior == "valid"), result.evidence()
    observed = json.loads((result.run_dir / "workspace_final/fixture-observation.json").read_text())
    assert (observed["uid"], observed["gid"]) == (os.geteuid(), os.getegid())
    assert observed["sudo"] is sudo
    assert observed["initializer"] and observed["prompt"]
    if behavior == "timeout":
        assert result.agent_outcome.timed_out
    if behavior == "invalid":
        assert result.proposal_status == "invalid"
    if behavior == "valid":
        assert result.gate.steps_run == ["test", "docs", "lint"]
    state = json.loads((result.run_dir / "host-state.json").read_text())
    assert all(row["removed"] for row in state["resources"])
    if state["gate_image"] is not None:
        assert (
            DockerEngine().request("GET", "/images/" + state["gate_image"] + "/json", missing=True)
            is None
        )
    engine = DockerEngine()
    assert engine.image(fixture_image)["Id"] == fixture_image
    for row in state["resources"]:
        assert engine.inspect(row["name"]) is None
    target = os.environ.get("SILVERQUILLM_QUALIFICATION")
    if target:
        destination = Path(target)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / (behavior + "-" + str(sudo) + ".json")).write_text(
            json.dumps(
                {
                    "definition": json.loads(path.read_text()),
                    "evidence": result.evidence(),
                    "observation": observed,
                    "cleanup": state,
                },
                indent=2,
            )
        )


def test_public_cli_and_scheduler_use_two_definitions_one_image_with_audited_grading(
    tmp_path, monkeypatch, fixture_image
):
    from click.testing import CliRunner

    from silverquillm import cli
    from silverquillm.candidate import load_candidate_bundle
    from silverquillm.results_repo import read_run_record
    from silverquillm.scheduler import load_state

    first = candidate(tmp_path, fixture_image, variant="cli")
    second = candidate(tmp_path, fixture_image, variant="scheduled")
    one, two = load_candidate_bundle(first), load_candidate_bundle(second)
    assert one.identity.image_digest == two.identity.image_digest
    assert one.candidate_hash != two.candidate_hash
    repo = tmp_path / "operator"
    repo.mkdir()
    (repo / "benchmarks").symlink_to(Path(__file__).resolve().parents[1] / "benchmarks")
    monkeypatch.setattr(cli, "_REPO_ROOT", repo)
    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "run",
            "--candidate",
            str(first),
            "--benchmark",
            "smoke",
            "--timeout",
            "30",
            "--results-dir",
            str(tmp_path / "cli-runs"),
            "--results-repo",
            str(tmp_path / "results"),
        ],
    )
    assert result.exit_code == 0, result.output + repr(result.exception)
    batches = repo / "batches"
    batches.mkdir()
    (batches / "fixture.toml").write_text(
        "[[runs]]\ncandidate = "
        + json.dumps(str(second))
        + '\nmode = "planned"\nbenchmark = "smoke"\nbudget_seconds = 30\n'
    )
    result = runner.invoke(
        cli.main,
        [
            "scheduler",
            "--once",
            "--batches-dir",
            str(batches),
            "--replay-without-state",
            "fixture",
            "--results-repo",
            str(tmp_path / "results"),
        ],
    )
    assert result.exit_code == 0, result.output + repr(result.exception)
    state = load_state(batches, "fixture")
    assert state.runs[0].state == "done" and state.runs[0].identity == two.identity.to_dict()
    records = [read_run_record(path.parent) for path in (tmp_path / "results").rglob("run.json")]
    # Locate by the actual versioned manifest name, independent of CLI output.
    if not records:
        from silverquillm.results_repo import MANIFEST_FILENAME

        records = [
            read_run_record(path.parent) for path in (tmp_path / "results").rglob(MANIFEST_FILENAME)
        ]
    assert len(records) == 2
    assert {row.candidate.definition_digest for row in records} == {
        one.identity.definition_digest,
        two.identity.definition_digest,
    }
    for record in records:
        assert not record.leaderboard_valid
        assert record.scores["engine_regression"]["evaluated"]
        assert record.scores["engine_regression"]["tests_total"] > 0
    assert DockerEngine().image(fixture_image)["Id"] == fixture_image


def test_interrupted_gate_is_reconciled_after_host_restart(tmp_path, monkeypatch, fixture_image):
    from silverquillm.docker_host import DockerHost, recover_resources

    class Interrupted(BaseException):
        pass

    path = candidate(tmp_path, fixture_image, variant="interrupted")
    run_id = "interrupted-" + uuid.uuid4().hex[:10]
    original_wait = DockerHost._wait

    def wait(host, resource, timeout):
        if resource["role"] == "gate":
            raise Interrupted()
        return original_wait(host, resource, timeout)

    monkeypatch.setattr(DockerHost, "_wait", wait)
    monkeypatch.setattr(DockerHost, "finish", lambda host: None)
    ref = benchmark(tmp_path)
    (ref.root / "workspace/.theozolith/gate.toml").write_text('[steps.test]\nrun="sleep 120"\n')
    with pytest.raises(Interrupted):
        contract.drive_contract_run(
            run_dir=tmp_path / run_id,
            run_id=run_id,
            benchmark=ref,
            mode=get_mode("basic"),
            budget_seconds=30,
            candidate=path,
        )
    state = json.loads((tmp_path / run_id / "host-state.json").read_text())
    engine = DockerEngine()
    try:
        assert any(
            row["role"] == "gate" and engine.inspect(row["name"])["State"]["Running"]
            for row in state["resources"]
        )
    finally:
        recovered = recover_resources(tmp_path / run_id, run_id, engine=engine)
    assert all(row["removed"] for row in recovered["resources"])
    assert all(engine.inspect(row["name"]) is None for row in recovered["resources"])
    assert engine.image(fixture_image)["Id"] == fixture_image
    assert not (tmp_path / run_id / "workspace_final").exists()
    recover_resources(tmp_path / run_id, run_id, engine=engine)
