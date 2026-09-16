import copy
import json
from pathlib import Path

import pytest
from karn.definition import canonical, new_definition

from silverquillm.contract import drive_contract_run
from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import BenchmarkRef
from silverquillm.modes import get_mode
from silverquillm.results_repo import DEFINITION_SCHEME, read_run_record

IMAGE = "sha256:" + "1" * 64
PROPOSAL = {
    "schema_version": 1,
    "mode": "run",
    "fields": {
        "pr-title": "Implement fixture",
        "pr-description": "Exercise the standalone interface.",
        "commit-message": "Implement fixture\n\nPreserve the benchmark contract.",
        "decisions": [{"what": "Use declared files", "why": "Keep the host independent."}],
    },
}


def definition(tmp_path, *, main=None):
    value = new_definition(
        name="fixture",
        mode="automaton",
        image=IMAGE,
        main=main or ["/bin/true"],
        definition_version=3,
    ).document
    value["runtime"]["mounts"] = [
        {
            "name": name,
            "target": target,
            "source": {"kind": "runtime", "value": name},
            "persistent": False,
            "access": "read_only" if name == "input" else "read_write",
            "purpose": name,
        }
        for name, target in [("workspace", "/work"), ("input", "/in"), ("output", "/out")]
    ]
    value["runtime"]["files"] = [
        {
            "name": "prompt",
            "mount": "input",
            "path": "task/prompt.md",
            "direction": "input",
            "schema": {"type": "string"},
        },
        {
            "name": "proposal",
            "mount": "output",
            "path": "answer/proposal.json",
            "direction": "output",
            "schema": {"type": "object"},
        },
    ]
    path = tmp_path / "definition.json"
    path.write_bytes(canonical(value))
    return path


def benchmark(tmp_path):
    root = tmp_path / "benchmark"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "seed.py").write_text("original = True\n")
    (workspace / ".theozolith").mkdir()
    (workspace / ".theozolith/gate.toml").write_text(
        '[steps.lint]\nrun="lint-command"\n[steps.test]\nrun="test-command"\n[steps.docs]\nrun="docs-command"\n'
    )
    return BenchmarkRef(
        "fixture",
        root,
        {
            "id": "fixture",
            "display_name": "Fixture",
            "draft_set": {"primary_set_code": "FDN"},
            "cards": ["1"],
            "leaderboard": {"eligible": False},
        },
    )


class Engine:
    def __init__(self, *, proposal=PROPOSAL, exit_code=0):
        self.containers = {}
        self.images = {IMAGE: {"Id": IMAGE, "Os": "linux"}}
        self.calls = []
        self.proposal = proposal
        self.exit_code = exit_code

    def available(self):
        return "fixture-engine"

    def image(self, reference):
        return copy.deepcopy(self.images[reference])

    def inspect(self, reference):
        result = self.containers.get(reference) or next(
            (r for r in self.containers.values() if r["Name"] == reference), None
        )
        return copy.deepcopy(result)

    def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path, copy.deepcopy(body)))
        if path.startswith("/containers/create"):
            identifier = f"{len(self.calls):064x}"
            self.containers[identifier] = {
                "Id": identifier,
                "Name": path.split("name=")[1],
                "Image": body["Image"],
                "Config": body,
                "State": {"Running": False, "ExitCode": None},
            }
            return {"Id": identifier}
        if path.startswith("/commit?"):
            image = "sha256:" + "2" * 64
            self.images[image] = {"Id": image, "Os": "linux", "Config": body}
            return {"Id": image}
        if path.startswith("/images/") and method == "GET":
            from urllib.parse import unquote

            return copy.deepcopy(self.images.get(unquote(path[len("/images/") : -len("/json")])))
        if path.startswith("/images/") and method == "DELETE":
            self.images.pop("sha256:" + "2" * 64)
            return None
        identifier = path.split("/")[2].split("?")[0]
        row = self.containers.get(identifier)
        if path.endswith("/start"):
            config = row["Config"]
            gate = config["Labels"]["silverquillm.construct.role"] == "gate"
            row["State"] = {"Running": False, "ExitCode": 0 if gate else self.exit_code}
            if not gate:
                mounts = {r["Target"]: Path(r["Source"]) for r in config["HostConfig"]["Mounts"]}
                (mounts["/work"] / "answer.py").write_text("answer = 42\n")
                if self.proposal is not None:
                    (mounts["/out"] / "answer/proposal.json").write_text(json.dumps(self.proposal))
            return None
        if "/logs?" in path:
            data = b"fixture output\n"
            return b"\x01\0\0\0" + len(data).to_bytes(4, "big") + data
        if path.endswith("/stop?t=2"):
            row["State"]["Running"] = False
            return None
        if method == "DELETE":
            self.containers.pop(identifier)
            return None
        raise AssertionError((method, path, body))


def run(tmp_path, monkeypatch, engine):
    from silverquillm import contract

    checked = []
    monkeypatch.setattr(
        contract,
        "evaluate_run",
        lambda run_dir, ref, timeout: checked.append((run_dir, ref)) or FullEvalResult(),
    )
    candidate = definition(tmp_path)
    ref = benchmark(tmp_path)
    result = drive_contract_run(
        run_dir=tmp_path / "run",
        run_id="run",
        benchmark=ref,
        mode=get_mode("planned"),
        budget_seconds=5,
        candidate=candidate,
        results_repo=tmp_path / "results",
        engine=engine,
    )
    return result, checked


def test_full_driver_uses_declared_files_isolated_gate_and_new_identity(tmp_path, monkeypatch):
    engine = Engine()
    result, checked = run(tmp_path, monkeypatch, engine)
    assert result.ok, result.evidence()
    assert result.gate.steps_run == ["test", "docs", "lint"]
    creates = [body for method, path, body in engine.calls if path.startswith("/containers/create")]
    assert [row["Cmd"][-1] for row in creates[1:]] == [
        "test-command",
        "docs-command",
        "lint-command",
    ]
    assert all(row["Entrypoint"] == ["/bin/sh"] for row in creates[1:])
    assert all("Source" not in row for row in result.evidence().get("input_hashes", {}))
    assert (
        "Before implementing, write a short plan"
        in (tmp_path / "run/job/input/task/prompt.md").read_text()
    )
    assert "`/out/answer/proposal.json`" in (tmp_path / "run/job/input/task/prompt.md").read_text()
    assert checked and (tmp_path / "run/workspace_final/answer.py").exists()
    record = read_run_record(result.record_dir)
    assert record.candidate.scheme == DEFINITION_SCHEME
    assert record.manifest_dict()["schema_version"] == 2
    assert not record.leaderboard_valid
    assert engine.containers == {} and set(engine.images) == {IMAGE}


@pytest.mark.parametrize("proposal,exit_code", [(None, 0), ({"bad": "shape"}, 0), (PROPOSAL, 7)])
def test_invalid_output_or_exit_is_not_success_but_partial_work_is_graded(
    tmp_path, monkeypatch, proposal, exit_code
):
    engine = Engine(proposal=proposal, exit_code=exit_code)
    result, checked = run(tmp_path, monkeypatch, engine)
    assert not result.ok
    assert checked and result.record_dir is not None
    assert engine.containers == {}


def test_unsupported_lifecycle_is_refused_before_any_engine_operation(tmp_path, monkeypatch):
    from silverquillm import contract

    path = definition(tmp_path)
    value = json.loads(path.read_text())
    value["runtime"]["backend"] = "kata"
    path.write_bytes(canonical(value))
    engine = Engine()
    result = contract.drive_contract_run(
        run_dir=tmp_path / "run",
        run_id="run",
        benchmark=benchmark(tmp_path),
        mode=get_mode("basic"),
        budget_seconds=5,
        candidate=path,
        engine=engine,
    )
    assert not result.ok and result.failure_class == "contract-unsupported"
    assert not engine.calls


@pytest.mark.parametrize(
    "source",
    ["/var/run/docker.sock", "/etc", "/driver.git", "../sibling", "/tmp/sibling-artifacts"],
)
def test_candidate_bind_declarations_cannot_select_host_resources(tmp_path, source):
    from silverquillm.docker_host import DockerHost, HostError

    doc = json.loads(definition(tmp_path).read_text())
    doc["runtime"]["mounts"][0]["source"] = {"kind": "bind", "value": source}
    with pytest.raises(HostError, match="external or host-only"):
        DockerHost.admit(doc)


def test_candidate_cannot_claim_sibling_persistent_storage(tmp_path):
    from silverquillm.docker_host import DockerHost, HostError

    doc = json.loads(definition(tmp_path).read_text())
    doc["runtime"]["mounts"][0]["persistent"] = True
    with pytest.raises(HostError, match="operator-owned"):
        DockerHost.admit(doc)


def test_recovery_prevalidates_every_resource_before_mutation(tmp_path, monkeypatch):
    from silverquillm.docker_host import OWNER_LABEL, DockerHost, HostError, recover_resources

    engine = Engine()
    original = DockerHost.finish
    monkeypatch.setattr(DockerHost, "finish", lambda host: None)
    result, _ = run(tmp_path, monkeypatch, engine)
    assert result.ok
    monkeypatch.setattr(DockerHost, "finish", original)
    last = list(engine.containers.values())[-1]
    last["Config"]["Labels"][OWNER_LABEL] = "different-owner"
    engine.calls.clear()
    with pytest.raises(HostError, match="ownership changed"):
        recover_resources(result.run_dir, result.run_id, engine=engine)
    assert not any(method in {"POST", "DELETE"} for method, *_ in engine.calls)


def test_restart_recovery_removes_gate_resources_and_preserves_candidate_image(
    tmp_path, monkeypatch
):
    from silverquillm.docker_host import DockerHost, recover_resources

    engine = Engine()
    monkeypatch.setattr(DockerHost, "finish", lambda host: None)
    result, _ = run(tmp_path, monkeypatch, engine)
    state = recover_resources(result.run_dir, result.run_id, engine=engine)
    assert all(row["removed"] for row in state["resources"])
    assert engine.containers == {} and set(engine.images) == {IMAGE}
    recover_resources(result.run_dir, result.run_id, engine=engine)


def test_lost_commit_reply_retains_inventory_until_owned_snapshot_is_observed(
    tmp_path, monkeypatch
):
    from silverquillm.docker_host import DockerHost, HostError, recover_resources

    engine = Engine()
    monkeypatch.setattr(DockerHost, "finish", lambda host: None)
    result, _ = run(tmp_path, monkeypatch, engine)
    path = result.run_dir / "host-state.json"
    state = json.loads(path.read_text())
    state["resources"] = state["resources"][:1]
    state["gate_image"] = None
    state["gate_commit_pending"] = True
    path.write_text(json.dumps(state))
    request = engine.request
    monkeypatch.setattr(
        engine,
        "request",
        lambda method, path, *a, **kw: (
            [] if path.startswith("/images/json?") else request(method, path, *a, **kw)
        ),
    )
    engine.calls.clear()
    with pytest.raises(HostError, match="snapshot creation is unconfirmed"):
        recover_resources(result.run_dir, result.run_id, engine=engine)
    assert not any(method in {"POST", "DELETE"} for method, *_ in engine.calls)
    assert json.loads(path.read_text())["gate_commit_pending"]


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "http://127.0.0.1/private"},
        {"$ref": "https://example.com/schema"},
        {"$ref": "file:///etc/private.json"},
        {"$ref": "relative.json"},
        {"allOf": [{"$ref": "file:///etc/private.json"}]},
        {"$defs": {"item": {"$dynamicRef": "https://example.com/schema"}}, "$ref": "#/$defs/item"},
        {"$id": "https://example.com/root", "$ref": "relative.json"},
        {"$id": "file:///etc/root.json", "allOf": [{"$dynamicRef": "relative.json"}]},
        {
            "$schema": "https://json-schema.org/draft/2019-09/schema",
            "$recursiveRef": "file:///etc/private.json",
        },
    ],
)
def test_external_schema_references_cannot_trigger_host_io(tmp_path, monkeypatch, schema):
    import urllib.request

    from silverquillm import contract

    calls = []
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **kw: (
            calls.append(a) or (_ for _ in ()).throw(AssertionError("host retrieval attempted"))
        ),
    )
    candidate = definition(tmp_path)
    doc = json.loads(candidate.read_text())
    doc["runtime"]["files"][0]["schema"] = schema
    candidate.write_text(json.dumps(doc))
    engine = Engine()
    result = contract.drive_contract_run(
        run_dir=tmp_path / "run",
        run_id="run",
        candidate=candidate,
        benchmark=benchmark(tmp_path),
        mode=get_mode("basic"),
        budget_seconds=5,
        engine=engine,
    )
    assert result.failure_class == "candidate"
    assert "payload_schema" in result.failure.reason
    assert not engine.calls and not calls


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "file:///etc/private.json"},
        {"allOf": [{"$dynamicRef": "http://127.0.0.1/private"}]},
        {"$id": "https://example.com/root", "$ref": "relative.json"},
        {"$id": "file:///etc/root.json", "$dynamicRef": "relative.json"},
    ],
)
def test_closed_registry_blocks_retrieval_even_without_admission(monkeypatch, schema):
    import urllib.request

    from jsonschema.exceptions import _WrappedReferencingError

    from silverquillm.docker_host import validate_payload

    calls = []
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **kw: (
            calls.append(a) or (_ for _ in ()).throw(AssertionError("host retrieval attempted"))
        ),
    )
    with pytest.raises(_WrappedReferencingError):
        validate_payload(schema, "prompt")
    assert not calls


@pytest.mark.parametrize(
    "schema",
    [
        {"$defs": {"text": {"type": "string"}}, "$ref": "#/$defs/text"},
        {
            "$id": "https://example.com/root",
            "$defs": {"text": {"type": "string"}},
            "$ref": "#/$defs/text",
        },
        {"$defs": {"text": {"$dynamicAnchor": "text", "type": "string"}}, "$dynamicRef": "#text"},
        {"type": "string", "examples": [{"$ref": "file:///annotation-is-data"}]},
        {"type": "string", "$recursiveRef": "file:///not-an-active-2020-keyword"},
    ],
)
def test_supported_local_and_dynamic_fragments_and_inactive_annotations(
    tmp_path, monkeypatch, schema
):
    import urllib.request

    from karn.definition import decode

    from silverquillm.docker_host import validate_payload

    calls = []
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **kw: (
            calls.append(a) or (_ for _ in ()).throw(AssertionError("host retrieval attempted"))
        ),
    )
    path = definition(tmp_path)
    doc = json.loads(path.read_text())
    doc["runtime"]["files"][0]["schema"] = schema
    decode(canonical(doc))
    validate_payload(schema, "prompt")
    assert not calls
