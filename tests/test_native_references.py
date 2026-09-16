"""Offline real native CLI qualification; no inference or login is performed."""

import json
import os
import uuid
from pathlib import Path

import pytest
from karn.definition import canonical

from silverquillm import contract
from silverquillm.docker_host import DockerEngine
from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import BenchmarkRef
from silverquillm.modes import get_mode

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("adapter,version", [("claude", "2.1.260"), ("codex", "0.153.4")])
def test_real_pinned_cli_bootstrap_and_declared_file_adapter(
    tmp_path, monkeypatch, adapter, version
):
    artifacts = os.environ.get("SILVERQUILLM_NATIVE_REFERENCES")
    if not artifacts:
        pytest.skip("build reference-recipes/build.py and set SILVERQUILLM_NATIVE_REFERENCES")
    original = json.loads((Path(artifacts) / (adapter + "-definition.json")).read_text())
    doc = json.loads(json.dumps(original))
    doc["runtime"]["main"].append("--check")
    doc["runtime"]["network"]["mode"] = "none"
    doc["runtime"]["credentials"] = []
    candidate = tmp_path / "offline-definition.json"
    candidate.write_bytes(canonical(doc))
    root = tmp_path / "benchmark"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "seed.py").write_text("seed = True\n")
    (workspace / ".theozolith").mkdir()
    (workspace / ".theozolith/gate.toml").write_text(
        '[steps.test]\nrun="python3 -m pytest --version"\n[steps.docs]\nrun="test -s native-version.json"\n[steps.lint]\nrun="'
        + adapter
        + ' --version"\n'
    )
    benchmark = BenchmarkRef(
        "offline",
        root,
        {
            "cards": ["1"],
            "draft_set": {"primary_set_code": "FDN"},
            "leaderboard": {"eligible": False},
        },
    )
    monkeypatch.setattr(contract, "evaluate_run", lambda *a, **kw: FullEvalResult())
    run_id = "native-" + adapter + "-" + uuid.uuid4().hex[:10]
    result = contract.drive_contract_run(
        run_dir=tmp_path / run_id,
        run_id=run_id,
        candidate=candidate,
        benchmark=benchmark,
        mode=get_mode("basic"),
        budget_seconds=60,
        results_repo=tmp_path / "results",
        environ={},
    )
    assert result.ok, result.evidence()
    observed = json.loads((result.run_dir / "workspace_final/native-version.json").read_text())
    assert version in observed["version"]
    assert (observed["uid"], observed["gid"]) == (os.geteuid(), os.getegid())
    assert observed["prompt_bytes"] > 0
    assert result.gate.steps_run == ["test", "docs", "lint"]
    engine = DockerEngine()
    state = json.loads((result.run_dir / "host-state.json").read_text())
    assert all(engine.inspect(row["name"]) is None for row in state["resources"])
    assert engine.image(original["image"])["Id"] == original["image"]
    output = Path(artifacts) / (adapter + "-offline-qualification.json")
    output.write_text(
        json.dumps(
            {
                "qualification": "offline-only; no inference or login",
                "selected_definition": original,
                "qualified_definition": doc,
                "evidence": result.evidence(),
                "observation": observed,
                "cleanup": state,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


@pytest.mark.parametrize(
    "adapter,host_key,guest_key",
    [
        ("claude", "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
        ("codex", "OPENAI_API_KEY", "CODEX_API_KEY"),
    ],
)
def test_real_host_delivers_only_selected_raw_binding_and_redacts_durable_output(
    tmp_path, adapter, host_key, guest_key
):
    import hashlib

    artifacts = os.environ.get("SILVERQUILLM_NATIVE_REFERENCES")
    if not artifacts:
        pytest.skip("build native references first")
    doc = json.loads((Path(artifacts) / (adapter + "-definition.json")).read_text())
    token = "synthetic-issue-184-raw-value-" + adapter
    digest = hashlib.sha256(token.encode()).hexdigest()
    doc["runtime"]["network"]["mode"] = "none"
    doc["runtime"]["environment"]["EXPECTED_DIGEST"] = digest
    program = (
        "import hashlib,json,os; from pathlib import Path; "
        "value=os.environ[" + repr(guest_key) + "]; "
        "assert hashlib.sha256(value.encode()).hexdigest()==os.environ['EXPECTED_DIGEST']; "
        "print(value,flush=True); "
        "Path('/workspace/delivery.json').write_text(json.dumps({'delivered':True})); "
        "Path('/output/proposal.json').write_text(json.dumps({'schema_version':1,'mode':'run','fields':"
        "{'pr-title':'Qualify raw delivery','pr-description':'Synthetic credential only.',"
        "'commit-message':'Qualify raw delivery','decisions':[{'what':'Use explicit environment delivery','why':'No login state is needed.'}]}}))"
    )
    doc["runtime"]["main"] = ["python3", "-c", program]
    candidate = tmp_path / "raw-definition.json"
    candidate.write_bytes(canonical(doc))
    root = tmp_path / "benchmark"
    (root / "workspace").mkdir(parents=True)
    (root / "workspace/seed.py").write_text("seed=True\n")
    benchmark = BenchmarkRef(
        "raw",
        root,
        {
            "cards": ["1"],
            "draft_set": {"primary_set_code": "FDN"},
            "leaderboard": {"eligible": False},
        },
    )
    run_id = "raw-" + adapter + "-" + uuid.uuid4().hex[:10]
    result = contract.drive_contract_run(
        run_dir=tmp_path / run_id,
        run_id=run_id,
        candidate=candidate,
        benchmark=benchmark,
        mode=get_mode("basic"),
        budget_seconds=30,
        environ={host_key: token},
        results_repo=tmp_path / "results",
    )
    assert result.ok, result.evidence()
    assert json.loads((result.run_dir / "workspace_final/delivery.json").read_text())["delivered"]
    assert "[redacted credential]" in (result.run_dir / "container-stdout.txt").read_text()
    for path in tmp_path.rglob("*"):
        if path.is_file() and not path.is_symlink():
            assert token.encode() not in path.read_bytes(), str(path.relative_to(tmp_path))
    state = json.loads((result.run_dir / "host-state.json").read_text())
    assert all(DockerEngine().inspect(row["name"]) is None for row in state["resources"])


@pytest.mark.parametrize(
    "adapter,host_key", [("claude", "ANTHROPIC_API_KEY"), ("codex", "OPENAI_API_KEY")]
)
def test_pinned_native_cli_uses_raw_key_against_loopback_only(tmp_path, adapter, host_key):
    import hashlib

    artifacts = os.environ.get("SILVERQUILLM_NATIVE_REFERENCES")
    if not artifacts:
        pytest.skip("build native references first")
    doc = json.loads((Path(artifacts) / (adapter + "-definition.json")).read_text())
    token = "synthetic-loopback-native-auth-" + adapter
    doc["runtime"]["network"]["mode"] = "none"
    doc["runtime"]["environment"].update(
        EXPECTED_DIGEST=hashlib.sha256(token.encode()).hexdigest(), PROBE_ADAPTER=adapter
    )
    doc["runtime"]["main"] = [
        "python3",
        "-c",
        (Path(__file__).parent / "fixtures/standalone/native_auth_probe.py").read_text(),
    ]
    candidate = tmp_path / "definition.json"
    candidate.write_bytes(canonical(doc))
    root = tmp_path / "benchmark"
    (root / "workspace").mkdir(parents=True)
    (root / "workspace/seed.py").write_text("seed=True\n")
    benchmark = BenchmarkRef(
        "raw",
        root,
        {
            "cards": ["1"],
            "draft_set": {"primary_set_code": "FDN"},
            "leaderboard": {"eligible": False},
        },
    )
    run_id = "native-auth-" + adapter + "-" + uuid.uuid4().hex[:10]
    result = contract.drive_contract_run(
        run_dir=tmp_path / run_id,
        run_id=run_id,
        candidate=candidate,
        benchmark=benchmark,
        mode=get_mode("basic"),
        budget_seconds=30,
        environ={host_key: token},
        results_repo=tmp_path / "results",
    )
    assert result.ok, result.evidence()
    observation = json.loads((result.run_dir / "workspace_final/native-auth.json").read_text())
    assert observation["matched"] and observation["requests"] > 0
    for path in tmp_path.rglob("*"):
        if path.is_file() and not path.is_symlink():
            assert token.encode() not in path.read_bytes()
    (Path(artifacts) / (adapter + "-native-auth.json")).write_text(
        json.dumps(
            {"observation": observation, "evidence": result.evidence()}, indent=2, sort_keys=True
        )
        + "\n"
    )
