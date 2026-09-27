from __future__ import annotations

import base64
import json
import shutil
import socket
import subprocess
import sys
import threading
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.karn.definition import KarnError, canonical, digest, inspect_image, load_candidate
from silverquillm.karn.docker import RUN_LABEL, Docker
from silverquillm.karn.host import DEFAULT_BUDGET_SECONDS, DockerHost, validate_budget
from silverquillm.karn.login import LoginProfile
from silverquillm.karn.proxy import ProxyServer, resolve_public

FIXTURES = Path(__file__).parent / "fixtures/karn"


def make_candidate(
    tmp_path,
    *,
    image=None,
    main=None,
    initializer=False,
    bootstrap=False,
    network=None,
    timeout=None,
):
    value = json.loads(
        (FIXTURES / "wire-vectors-v4/canonical-definition-id/input.json").read_bytes()
    )
    value["image"] = image or "sha256:" + "1" * 64
    value["runtime"].update(
        main=main or ["python3", "-c", "pass"],
        initializer=None,
        initializer_runner=None,
        bootstrap=None,
        timeout_seconds=timeout,
        plugins=[],
        credentials=[],
        environment={},
        network=network or {"mode": "none", "https_hosts": []},
    )
    mounts = []
    for name, readonly in (
        ("workspace", False),
        ("input", True),
        ("output", False),
        ("bootstrap", False),
    ):
        mounts.append(
            {
                "name": name,
                "target": "/" + name,
                "source": {"kind": "runtime", "value": name},
                "purpose": name,
                "persistent": False,
                "access": "read_only" if readonly else "read_write",
            }
        )
    value["runtime"]["mounts"] = mounts
    value["runtime"]["files"] = [
        {
            "name": "prompt",
            "mount": "input",
            "path": "task.txt",
            "direction": "input",
            "schema": True,
        },
        {
            "name": "result",
            "mount": "output",
            "path": "result.json",
            "direction": "output",
            "schema": True,
        },
    ]
    if initializer:
        value["runtime"]["initializer"] = [
            "python3",
            "-c",
            "import pathlib; pathlib.Path('/workspace/init.txt').write_text('initialized')",
        ]
        value["runtime"]["initializer_runner"] = [
            "python3",
            "/run/silverquillm/fixtures/run-initializer.py",
        ]
    if bootstrap:
        value["runtime"]["bootstrap"] = {
            "argv": [
                "/usr/local/bin/python3",
                "-I",
                "/run/silverquillm/fixtures/account-bootstrap.py",
            ],
            "protocol": "identity-v2",
            "identity_input": "/bootstrap/identity.json",
            "handoff": "/bootstrap/handoff.json",
            "home": "/home/agent",
            "shell": "/bin/bash",
        }
        value["runtime"]["files"] += [
            {
                "name": "identity",
                "mount": "bootstrap",
                "path": "identity.json",
                "direction": "input",
                "schema": True,
            },
            {
                "name": "handoff",
                "mount": "bootstrap",
                "path": "handoff.json",
                "direction": "status",
                "schema": True,
            },
        ]
    path = tmp_path / "build/constructs/bare/definition.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(canonical(value))
    return load_candidate(
        tmp_path / "build",
        "bare",
        image_inspector=inspect_image if image else lambda ref: {"Id": ref},
    )


class FakeDocker:
    def __init__(self, *, running=False, fail_start=False):
        self.commands = []
        self.running, self.fail_start = running, fail_start
        self.created = False
        self.stopped = False
        self.removed = False

    def inspect_image(self, reference):
        return {"Id": reference}

    def command(self, *args, **kwargs):
        self.commands.append(args)
        if args[0] == "create":
            self.created = True
        if args[0] == "start" and self.fail_start:
            raise KarnError("docker_command_failed:start")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    def inspect_container(self, name):
        return {"State": {"Running": self.running, "ExitCode": 0}}

    def stop_and_confirm(self, name, run_id):
        self.stopped = True
        self.running = False

    def logs(self, name, stdout, stderr, limits, **kwargs):
        stdout.write_bytes(b"native log")
        stderr.write_bytes(b"")

    def remove(self, name):
        self.removed = True

    def cleanup_run(self, container_name, run_id):
        self.commands.append(("cleanup", container_name, run_id))


def test_budget_default_is_large_and_shorter_definition_refuses_before_launch(tmp_path):
    candidate = make_candidate(tmp_path, timeout=60)
    assert DEFAULT_BUDGET_SECONDS == 86400
    docker = FakeDocker()
    with pytest.raises(KarnError, match="definition_timeout_shorter_than_budget"):
        DockerHost(docker=docker).run(candidate, tmp_path / "workspace", tmp_path / "run", "task")
    assert docker.commands == []
    validate_budget(candidate, 60)


def test_declared_inputs_and_immutable_image_launch_without_proposal_gate(tmp_path):
    candidate = make_candidate(tmp_path)
    docker = FakeDocker()
    result = DockerHost(docker=docker).run(
        candidate, tmp_path / "workspace", tmp_path / "run", "Implement cards"
    )
    assert result.status == "completed"
    assert result.result_document is None
    assert result.workspace_stopped
    assert (tmp_path / "run/mounts/input/task.txt").read_text() == "Implement cards"
    create = docker.commands[0]
    assert create[create.index("--entrypoint") + 2] == candidate.image_id
    assert "--pull" in create and "never" in create
    assert not any(command[0] in ("build", "pull") for command in docker.commands)
    assert docker.stopped and docker.removed


def test_deadline_stops_before_observing_partial_workspace(tmp_path, monkeypatch):
    candidate = make_candidate(tmp_path)
    docker = FakeDocker(running=True)
    ticks = iter([0.0, 2.0])
    monkeypatch.setattr("silverquillm.karn.host.time.monotonic", lambda: next(ticks))
    observed = []

    def observe(result, native):
        assert docker.stopped and result.workspace_stopped
        observed.append(result.status)

    result = DockerHost(docker=docker).run(
        candidate,
        tmp_path / "workspace",
        tmp_path / "run",
        "task",
        budget_seconds=1,
        after_stop=observe,
    )
    assert result.status == "deadline"
    assert observed == ["deadline"]


def test_start_failure_is_recorded_and_container_stopped(tmp_path):
    candidate = make_candidate(tmp_path)
    docker = FakeDocker(fail_start=True)
    result = DockerHost(docker=docker).run(
        candidate, tmp_path / "workspace", tmp_path / "run", "task"
    )
    assert result.status == "host_failed"
    assert result.failure_stage == "launch"
    assert result.error == "docker_command_failed:start"
    assert docker.stopped and result.workspace_stopped


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1"])
def test_restricted_proxy_refuses_private_destinations(address, monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    )
    with pytest.raises(ValueError, match="nonpublic_destination"):
        resolve_public("permitted.example", 443)


def test_recovery_will_not_stop_unrelated_container():
    docker = Docker()
    docker.inspect_container = lambda _: {
        "Config": {"Labels": {RUN_LABEL: "different"}},
        "State": {"Running": True},
    }
    with pytest.raises(KarnError, match="container_recovery_identity_mismatch"):
        docker.stop_and_confirm("some-container", "expected")


@pytest.fixture
def local_image():
    result = subprocess.run(
        ["docker", "image", "inspect", "python:3.13-slim"], capture_output=True, check=False
    )
    if result.returncode:
        pytest.skip("requires local python:3.13-slim image; tests never pull")
    return json.loads(result.stdout)[0]["Id"]


@pytest.mark.integration
def test_real_docker_bootstrap_initializer_and_implementation_only_output(tmp_path, local_image):
    command = "import os,pathlib; assert os.getuid()!=0; assert pathlib.Path('/workspace/init.txt').exists(); pathlib.Path('/workspace/implementation.py').write_text('answer=42'); print('finished')"
    candidate = make_candidate(
        tmp_path,
        image=local_image,
        main=["python3", "-c", command],
        initializer=True,
        bootstrap=True,
    )
    result = DockerHost().run(
        candidate,
        tmp_path / "workspace",
        tmp_path / "run",
        "Implement",
        budget_seconds=30,
        extra_mounts=[
            {
                "Type": "bind",
                "Source": str(FIXTURES / "runtime"),
                "Target": "/run/silverquillm/fixtures",
                "ReadOnly": True,
            }
        ],
    )
    assert result.status == "completed", result.to_dict()
    assert result.workspace_stopped
    assert not result.observation_errors
    assert (tmp_path / "workspace/implementation.py").read_text() == "answer=42"
    assert "finished" in (tmp_path / "run/stdout.log").read_text()


@pytest.mark.integration
def test_real_docker_deadline_includes_initializer_and_retains_partial_work(tmp_path, local_image):
    candidate = make_candidate(
        tmp_path,
        image=local_image,
        main=["python3", "-c", "raise AssertionError('main must not start')"],
        initializer=True,
    )
    candidate.runtime["initializer"] = [
        "python3",
        "-c",
        "import pathlib,time; pathlib.Path('/workspace/partial.py').write_text('partial'); time.sleep(60)",
    ]
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    candidate = load_candidate(candidate.build_output, "bare")
    result = DockerHost().run(
        candidate,
        tmp_path / "workspace",
        tmp_path / "run",
        "Implement",
        budget_seconds=1,
        extra_mounts=[
            {
                "Type": "bind",
                "Source": str(FIXTURES / "runtime"),
                "Target": "/run/silverquillm/fixtures",
                "ReadOnly": True,
            }
        ],
    )
    assert result.status == "deadline", result.to_dict()
    assert result.workspace_stopped
    assert (tmp_path / "workspace/partial.py").read_text() == "partial"


@pytest.mark.integration
def test_real_restricted_network_blocks_direct_egress_and_unlisted_proxy(tmp_path, local_image):
    command = r"""import os,socket,urllib.parse,pathlib
try:
    socket.create_connection(('1.1.1.1',443),2)
except OSError:
    pass
else:
    raise AssertionError('direct egress available')
p=urllib.parse.urlsplit(os.environ['HTTPS_PROXY'])
s=socket.create_connection((p.hostname,p.port),2)
s.sendall(b'CONNECT forbidden.example:443 HTTP/1.1\r\nHost: forbidden.example:443\r\n\r\n')
assert b'403 Forbidden' in s.recv(4096)
pathlib.Path('/workspace/network-checked').write_text('restricted')
"""
    candidate = make_candidate(
        tmp_path,
        image=local_image,
        main=["python3", "-c", command],
        network={"mode": "restricted", "https_hosts": ["api.openai.com"]},
    )
    result = DockerHost().run(
        candidate, tmp_path / "workspace", tmp_path / "run", "task", budget_seconds=15
    )
    assert result.status == "completed", result.to_dict()
    assert (tmp_path / "workspace/network-checked").exists()


def test_observation_bug_does_not_skip_cleanup_or_final_record(tmp_path):
    candidate = make_candidate(tmp_path)
    docker = FakeDocker()

    def broken_observer(*args):
        raise RuntimeError("collector implementation error")

    result = DockerHost(docker=docker).run(
        candidate, tmp_path / "workspace", tmp_path / "run", "task", after_stop=broken_observer
    )
    assert result.status == "completed"
    assert result.observation_errors == ["after_stop_observation_failed"]
    assert docker.stopped and docker.removed
    assert (tmp_path / "run/host-result.json").exists()


def test_host_overrides_cannot_silently_replace_model_or_workspace(tmp_path):
    candidate = make_candidate(tmp_path)
    docker = FakeDocker()
    host = DockerHost(docker=docker)
    with pytest.raises(KarnError, match="undeclared_runtime_environment_override"):
        host.run(
            candidate,
            tmp_path / "workspace",
            tmp_path / "run",
            "task",
            extra_environment={"CONSTRUCT_MODEL": "other"},
        )
    with pytest.raises(KarnError, match="infrastructure_mount_must_be_readonly_and_scoped"):
        host.run(
            candidate,
            tmp_path / "workspace",
            tmp_path / "run",
            "task",
            extra_mounts=[
                {"Type": "bind", "Source": str(tmp_path), "Target": "/workspace", "ReadOnly": False}
            ],
        )
    assert docker.commands == []


@pytest.mark.integration
def test_real_login_harvest_survives_observer_bug_and_redacts_log_credentials(
    tmp_path, local_image
):
    if sys.version_info[:2] != (3, 13):
        pytest.skip("The pinned Plugin SDK requires CPython 3.13")
    candidate = make_candidate(
        tmp_path,
        image=local_image,
        main=[
            "python3",
            "-c",
            "import json,pathlib; p=pathlib.Path('/native/auth.json'); value=json.loads(p.read_text()); value['tokens']['access_token']='refreshed-secret-value'; p.write_text(json.dumps(value)); print(value['tokens']['access_token']); pathlib.Path('/workspace/partial.py').write_text('saved')",
        ],
    )
    shutil.copytree(FIXTURES / "login-build/plugins", candidate.build_output / "plugins")
    manifest = json.loads(
        (candidate.build_output / "plugins/karn-codex-login-0.1.0/install.json").read_text()
    )["manifest"]
    candidate.runtime["plugins"] = [
        {
            "id": manifest["id"],
            "version": manifest["version"],
            "source": "catalog",
            "artifact": digest(canonical(manifest, ascii_only=True)),
        }
    ]
    candidate.runtime["environment"]["CODEX_HOME"] = "/native"
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    candidate = load_candidate(candidate.build_output, "bare")
    profile = LoginProfile(tmp_path / "private-login", "research")
    auth = canonical(
        {
            "tokens": {
                key: "synthetic-" + key
                for key in ("access_token", "refresh_token", "id_token", "account_id")
            }
        }
    )
    profile.set_secret(
        "login.research",
        canonical(
            {
                "format": 1,
                "revision": "a" * 32,
                "files": {"auth.json": base64.b64encode(auth).decode()},
            }
        ).decode(),
    )
    observed = []

    def observe(result, native):
        assert result.workspace_stopped
        assert (native / "auth.json").exists()
        observed.append(native)
        raise RuntimeError("injected collector failure")

    result = DockerHost(plugin_cache=tmp_path / "plugin-cache", plugin_python=sys.executable).run(
        candidate,
        tmp_path / "workspace",
        tmp_path / "run",
        "Implement",
        budget_seconds=20,
        login_profile=profile,
        after_stop=observe,
    )
    assert result.status == "completed", result.to_dict()
    assert result.observation_errors == ["after_stop_observation_failed"]
    assert len(observed) == 1 and not observed[0].exists()
    assert profile.pending() is None
    saved = json.loads(profile.get_secret("login.research"))
    assert (
        json.loads(base64.b64decode(saved["files"]["auth.json"]))["tokens"]["access_token"]
        == "refreshed-secret-value"
    )
    assert "refreshed-secret-value" not in (tmp_path / "run/stdout.log").read_text()
    assert "[REDACTED]" in (tmp_path / "run/stdout.log").read_text()


def test_result_must_match_declared_schema(tmp_path):
    candidate = make_candidate(tmp_path)
    candidate.runtime["files"][1]["schema"] = {"type": "object", "required": ["outcome"]}
    candidate.definition_path.write_bytes(canonical(candidate.definition))
    candidate = load_candidate(
        candidate.build_output, "bare", image_inspector=lambda ref: {"Id": ref}
    )
    docker = FakeDocker()
    original = docker.command

    def command(*args, **kwargs):
        if args[0] == "start":
            (tmp_path / "run/mounts/output/result.json").write_text('{"unstructured":"output"}')
        return original(*args, **kwargs)

    docker.command = command
    result = DockerHost(docker=docker).run(
        candidate, tmp_path / "workspace", tmp_path / "run", "task"
    )
    assert result.status == "completed"
    assert result.result_document is None
    assert "result_schema_mismatch" in result.observation_errors


def test_otlp_relay_forwards_only_the_fixed_collector_endpoint():
    received = []

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    collector = HTTPServer(("127.0.0.1", 0), Collector)
    endpoint = f"http://127.0.0.1:{collector.server_port}/v1/logs"
    proxy = ProxyServer(("127.0.0.1", 0), [], endpoint)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in (collector, proxy)
    ]
    for thread in threads:
        thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{proxy.server_address[1]}/v1/logs",
            data=b'{"resourceLogs":[]}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            assert response.read() == b"{}"
        assert received == [("/v1/logs", b'{"resourceLogs":[]}')]
        with socket.create_connection(proxy.server_address, timeout=3) as client:
            client.sendall(b"POST /private HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
            assert b"403 Forbidden" in client.recv(4096)
        assert len(received) == 1
    finally:
        for server in (proxy, collector):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join()


def test_recovery_preserves_network_owned_by_another_run():
    docker = Docker()
    docker.inspect_container = lambda _: None
    commands = []

    def command(*args, **kwargs):
        commands.append(args)
        return SimpleNamespace(
            returncode=0, stdout=canonical([{"Labels": {RUN_LABEL: "other-run"}}]), stderr=b""
        )

    docker.command = command
    with pytest.raises(KarnError, match="network_recovery_identity_mismatch"):
        docker.cleanup_run("sq-run-expected", "expected")
    assert commands == [("network", "inspect", "sq-net-expected")]


@pytest.mark.integration
def test_real_orphan_recovery_removes_only_owned_run_resources(local_image):
    docker = Docker()
    run_id = uuid.uuid4().hex
    workload, proxy, network = "sq-run-" + run_id, "sq-proxy-" + run_id, "sq-net-" + run_id
    unrelated = "sq-unrelated-" + run_id
    try:
        docker.command(
            "network", "create", "--internal", "--label", RUN_LABEL + "=" + run_id, network
        )
        for name in (workload, proxy, unrelated):
            docker.command(
                "create",
                "--pull",
                "never",
                "--name",
                name,
                "--label",
                RUN_LABEL + "=" + ("other" if name == unrelated else run_id),
                "--network",
                "none" if name == unrelated else network,
                "--entrypoint",
                "python3",
                local_image,
                "-c",
                "import time; time.sleep(60)",
            )
            docker.command("start", name)
        docker.stop_and_confirm(workload, run_id)
        docker.cleanup_run(workload, run_id)
        assert docker.inspect_container(workload) is None
        assert docker.inspect_container(proxy) is None
        assert docker.command("network", "inspect", network, check=False).returncode != 0
        assert docker.inspect_container(unrelated)["State"]["Running"]
    finally:
        for name in (workload, proxy, unrelated):
            docker.remove(name)
        docker.command("network", "rm", network, check=False)


@pytest.mark.parametrize(
    ("stderr", "error"),
    [
        (b"Error response from daemon: No such image: sha256:abc", "image_not_available_locally"),
        (b"permission denied while trying to connect to the docker API", "docker_unavailable"),
    ],
)
def test_image_inspection_tells_a_missing_image_from_an_unreachable_docker(
    monkeypatch, stderr, error
):
    monkeypatch.setattr(
        "silverquillm.karn.definition.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 1, b"", stderr),
    )
    with pytest.raises(KarnError, match="^" + error + "$"):
        inspect_image("sha256:" + "0" * 64)
