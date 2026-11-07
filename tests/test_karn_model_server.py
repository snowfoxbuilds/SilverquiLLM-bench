"""The local model server for pi constructs (issue #262), against a fake llama-server."""

from __future__ import annotations

import json
import socket
import sys
import threading
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.karn.definition import KarnError
from silverquillm.karn.docker import Network
from silverquillm.karn.model_server import (
    MODEL_SERVER_ENV,
    MODEL_SERVER_URL,
    ModelRelayCollector,
    ModelServerHost,
    file_sha256,
    model_server_spec,
    plan_model_server,
    summarize_model_events,
)
from silverquillm.karn.observations import summarize_events
from silverquillm.karn.proxy import ModelForwardServer

FAKE_SERVER = r"""
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
if "--version" in sys.argv:
    print("version: 0.9.0-dev (build 12182, commit fd27b2034)")
    sys.exit(0)
port = int(sys.argv[sys.argv.index("--port") + 1])
alias = sys.argv[sys.argv.index("--alias") + 1]
with open(sys.argv[0] + ".argv", "w") as out:
    json.dump(sys.argv[1:], out)

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *args):
        pass
    def do_GET(self):
        body = b"{}" if self.path == "/health" else json.dumps({"data": [{"id": alias}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        usage = {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
                 "prompt_tokens_details": {"cached_tokens": 60}}
        timings = {"cache_n": 60, "prompt_n": 40, "prompt_ms": 20.0,
                   "predicted_n": 7, "predicted_ms": 70.0}
        base = {"id": "chatcmpl-1", "model": alias, "object": "chat.completion.chunk"}
        if not request.get("stream"):
            body = json.dumps({**base, "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "done"}}],
                "usage": usage, "timings": timings}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        chunks = [
            {**base, "choices": [{"index": 0, "delta": {"reasoning_content": "think"}}]},
            {**base, "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "c1",
                "function": {"name": "bash", "arguments": "{\"command\":"}}]}}]},
            {**base, "choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0,
                "function": {"arguments": "\"ls\"}"}}]}}]},
            {**base, "choices": [{"index": 0, "finish_reason": "tool_calls", "delta": {}}]},
            {**base, "choices": [], "usage": usage, "timings": timings},
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for chunk in [*(b"data: " + json.dumps(c).encode() + b"\n\n" for c in chunks),
                      b"data: [DONE]\n\n"]:
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
        self.wfile.write(b"0\r\n\r\n")

ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def spec_document(**overrides):
    document = {
        "engine": "llama.cpp",
        "build": "b12182",
        "model": {"file": "model.gguf", "sha256": "0" * 64},
        "arguments": ["-c", "262144", "-ctk", "f16", "--jinja"],
    }
    document.update(overrides)
    return document


def runtime(document=None, *, mode="restricted", **environment):
    environment = {
        "CONSTRUCT_MODEL": "qwen3.8-27b",
        "CONSTRUCT_PI_BASE_URL": MODEL_SERVER_URL,
        MODEL_SERVER_ENV: json.dumps(spec_document() if document is None else document),
        **environment,
    }
    return {"environment": environment, "network": {"mode": mode, "https_hosts": []}}


@pytest.fixture
def served(tmp_path):
    """A fake llama-server build and a model file, as a host would configure them."""
    binary = tmp_path / "llama-server"
    binary.write_text("#!" + sys.executable + "\n" + FAKE_SERVER)
    binary.chmod(0o755)
    models = tmp_path / "models"
    models.mkdir()
    (models / "model.gguf").write_bytes(b"GGUF weights")
    document = spec_document(
        model={"file": "model.gguf", "sha256": file_sha256(models / "model.gguf")}
    )
    spec = model_server_spec(runtime(document))
    host = ModelServerHost(models, {"b12182": binary})
    return SimpleNamespace(binary=binary, spec=spec, host=host, state=tmp_path / "state")


def test_a_definition_without_a_model_server_has_none():
    assert model_server_spec({"environment": {}, "network": {"mode": "none"}}) is None


def test_the_spec_keeps_the_recipes_server_and_serves_its_construct_model():
    spec = model_server_spec(runtime())
    assert spec.served_model == "qwen3.8-27b"
    assert spec.arguments == ("-c", "262144", "-ctk", "f16", "--jinja")
    assert spec.to_dict()["model"] == {"file": "model.gguf", "sha256": "0" * 64}


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        (spec_document(engine="vllm"), "model_server_engine_unsupported"),
        (spec_document(build="12182"), "model_server_build_invalid"),
        (spec_document(model={"file": "../x.gguf", "sha256": "0" * 64}), "model_invalid"),
        (spec_document(model={"file": "m.gguf", "sha256": "abc"}), "model_invalid"),
        (spec_document(arguments=["--host", "0.0.0.0"]), "flag_not_allowed:--host"),
        (spec_document(arguments=["-m", "/etc/passwd"]), "flag_not_allowed:-m"),
        (spec_document(arguments=["--api-key", "x"]), "flag_not_allowed:--api-key"),
        (spec_document(arguments=["-c"]), "flag_value_missing:-c"),
        ({**spec_document(), "extra": 1}, "model_server_spec_invalid"),
    ],
)
def test_a_malformed_server_is_refused(document, reason):
    with pytest.raises(KarnError, match=reason):
        model_server_spec(runtime(document))


def test_the_workload_must_use_the_relay_address_on_a_restricted_network():
    with pytest.raises(KarnError, match="model_server_url_mismatch"):
        model_server_spec(runtime(CONSTRUCT_PI_BASE_URL="http://192.168.1.2:8080/v1"))
    with pytest.raises(KarnError, match="model_server_requires_restricted_network"):
        model_server_spec(runtime(mode="open"))
    with pytest.raises(KarnError, match="model_server_requires_construct_model"):
        model_server_spec(runtime(CONSTRUCT_MODEL=""))


def test_the_plan_checks_the_hosts_build_and_model_file(served):
    plan = plan_model_server(served.spec, served.host, served.state)
    assert plan.commit == "fd27b2034"
    assert plan.model_path == served.host.models_dir / "model.gguf"
    with pytest.raises(KarnError, match="model_server_build_unavailable:b12182"):
        plan_model_server(served.spec, ModelServerHost(served.host.models_dir, {}), served.state)
    other = ModelServerHost(served.host.models_dir, {"b12183": served.binary})
    with pytest.raises(KarnError, match="model_server_build_mismatch"):
        plan_model_server(
            model_server_spec(runtime(spec_document(build="b12183"))), other, served.state
        )
    missing = model_server_spec(
        runtime(spec_document(model={"file": "other.gguf", "sha256": "0" * 64}))
    )
    with pytest.raises(KarnError, match="model_file_unavailable:other.gguf"):
        plan_model_server(missing, served.host, served.state)
    with pytest.raises(KarnError, match="model_server_models_dir_unset"):
        plan_model_server(served.spec, ModelServerHost(None, served.host.llama_cpp), served.state)


def post(url, document):
    request = urllib.request.Request(
        url,
        data=json.dumps(document).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read()


def test_the_relay_streams_through_and_records_each_request(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        argv = json.loads(Path(str(served.binary) + ".argv").read_text())
        assert argv[argv.index("--host") + 1] == "127.0.0.1"
        assert argv[argv.index("--alias") + 1] == "qwen3.8-27b"
        assert argv[-5:] == ["-c", "262144", "-ctk", "f16", "--jinja"]
        assert collector.facts["model_sha256_verified"] is True
        status, body = post(
            collector.endpoint + "/v1/chat/completions",
            {
                "model": "qwen3.8-27b",
                "stream": True,
                "messages": [
                    {"role": "user", "content": "task"},
                    {"role": "assistant", "content": "earlier"},
                    {"role": "tool", "content": "output"},
                ],
            },
        )
        assert status == 200 and body.endswith(b"data: [DONE]\n\n")
        status, _ = post(
            collector.endpoint + "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "again"}]},
        )
        with pytest.raises(urllib.error.HTTPError) as refused:
            post(collector.endpoint + "/v1/completions", {})
        assert refused.value.code == 404
        measurements = collector.finalize(exit_kind="completed")
    assert collector.llama.process.poll() is not None
    first, second = measurements["requests"]
    assert first["model"] == "qwen3.8-27b" and first["thread_id"] == "main"
    assert first["usage"]["input_tokens"] == 100 and first["usage"]["cached_input_tokens"] == 60
    assert first["finish_reason"] == "tool_calls" and second["finish_reason"] == "stop"
    assert measurements["subagents"] == [] and measurements["subagent_threads"] == 0
    assert measurements["agent_turns"]["tool_calls"]["value"] == 1
    assert "model_price_unavailable" in measurements["estimated_cost"]["reasons"]
    timings = measurements["server_timings"]
    assert timings["generated_tokens"] == 14 and timings["generation_tokens_per_second"] == 100.0
    transcript = [json.loads(line) for line in (run_dir / "model-transcript.jsonl").open()]
    assert transcript[0]["new_messages"] == [{"role": "tool", "content": "output"}]
    assert transcript[0]["response"]["tool_calls"] == [
        {"id": "c1", "name": "bash", "arguments": '{"command":"ls"}'}
    ]
    assert transcript[0]["response"]["reasoning"] == "think"
    events = [json.loads(line) for line in (run_dir / "observations.events.jsonl").open()]
    assert (
        summarize_events(events, exit_kind="completed", adapter="model_server")["requests"]
        == measurements["requests"]
    )


def test_the_sidecar_forwards_only_v1_paths_to_the_relay(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    with ModelRelayCollector(tmp_path / "run", plan=plan) as collector:
        forward = ModelForwardServer(("127.0.0.1", 0), collector.endpoint)
        thread = threading.Thread(target=forward.serve_forever, daemon=True)
        thread.start()
        try:
            address = f"http://127.0.0.1:{forward.server_address[1]}"
            status, body = post(
                address + "/v1/chat/completions",
                {"stream": True, "messages": [{"role": "user", "content": "x"}]},
            )
            assert status == 200 and b'"usage"' in body
            for request in (
                b"GET /health HTTP/1.1\r\n\r\n",
                b"GET /v1/../health HTTP/1.1\r\n\r\n",
                b"CONNECT example.com:443 HTTP/1.1\r\n\r\n",
                b"POST /v1/chat/completions HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n",
            ):
                with socket.create_connection(forward.server_address, timeout=5) as client:
                    client.sendall(request)
                    assert b"403 Forbidden" in client.recv(4096)
        finally:
            forward.shutdown()
            forward.server_close()
            thread.join()
        assert len(collector.finalize(exit_kind="completed")["requests"]) == 1


def test_a_model_file_that_changed_is_refused_before_the_server_starts(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    (served.host.models_dir / "model.gguf").write_bytes(b"other weights")
    with pytest.raises(KarnError, match="model_digest_mismatch"):
        ModelRelayCollector(tmp_path / "run", plan=plan).__enter__()
    assert not Path(str(served.binary) + ".argv").exists()


def test_one_model_server_at_a_time_on_a_host(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    with (
        ModelRelayCollector(tmp_path / "first", plan=plan),
        pytest.raises(KarnError, match="model_server_busy"),
    ):
        ModelRelayCollector(tmp_path / "second", plan=plan).__enter__()


def test_failed_requests_and_an_unfinished_run_are_counted_not_hidden():
    events = [
        {
            "id": "a",
            "kind": "response",
            "response_id": "a",
            "status": 200,
            "model": "m",
            "usage": None,
            "timestamp_ms": 1,
            "tool_calls": 0,
        },
        {
            "id": "b",
            "kind": "response",
            "response_id": "b",
            "status": 502,
            "model": None,
            "error": "upstream_failed:OSError",
            "usage": None,
            "timestamp_ms": 2,
            "tool_calls": 0,
        },
    ]
    measurements = summarize_model_events(events, exit_kind="deadline")
    assert measurements["coverage"]["failed_requests"] == 1
    assert len(measurements["requests"]) == 1
    reasons = measurements["usage"]["reasons"]
    assert "response_usage_missing" in reasons and "execution_did_not_complete" in reasons


class NetworkDocker:
    def __init__(self):
        self.commands = []

    def command(self, *args, check=True):
        self.commands.append(args)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    def inspect_container(self, name):
        return {"NetworkSettings": {"Networks": {"sq-net-r1": {"IPAddress": "10.9.0.2"}}}}

    def remove(self, name):
        self.commands.append(("remove", name))


def test_the_sidecar_is_the_model_server_and_is_not_proxied(tmp_path):
    docker = NetworkDocker()
    policy = {"mode": "restricted", "https_hosts": []}
    with Network(
        docker, "r1", policy, "sha256:" + "1" * 64, tmp_path, model_endpoint="http://h:1/model/x"
    ) as network:
        assert network.hosts == {"model-server": "10.9.0.2"}
        assert network.environment["NO_PROXY"].endswith(",model-server")
        create = next(command for command in docker.commands if command[0] == "create")
        assert "SILVERQUILLM_MODEL_ENDPOINT=http://h:1/model/x" in create
        ready = next(command for command in docker.commands if command[0] == "exec")
        assert "(3128, 8080)" in ready[-1]
    with pytest.raises(KarnError, match="model_server_requires_restricted_network"):
        Network(
            docker,
            "r2",
            {"mode": "open", "https_hosts": []},
            "x",
            tmp_path,
            model_endpoint="http://h:1/model/x",
        ).__enter__()


def test_a_model_server_run_is_observed_by_its_relay_only():
    from silverquillm.karn.execution import select_native_telemetry

    candidate = SimpleNamespace(runtime=runtime())
    assert select_native_telemetry(candidate, "auto") == {
        "requested": "auto",
        "enabled": True,
        "source": "model_server",
        "adapter": "model_server",
    }
    with pytest.raises(KarnError, match="native_telemetry_unavailable_with_model_server"):
        select_native_telemetry(candidate, "codex")


def test_the_workload_resolves_model_server_without_dns(tmp_path):
    from silverquillm.karn.host import DockerHost

    docker = NetworkDocker()
    network = SimpleNamespace(
        network="sq-net-r1",
        policy={"mode": "restricted", "https_hosts": []},
        hosts={"model-server": "10.9.0.2"},
    )
    candidate = SimpleNamespace(
        runtime={
            "sudo": False,
            "bootstrap": None,
            "resources": {"cpus": None, "memory_bytes": None, "pids": None},
        },
        image_id="sha256:" + "1" * 64,
    )
    DockerHost(docker=docker)._create(
        candidate, "sq-run-r1", "r1", ["pi"], "1000:1000", [], network, {}
    )
    create = docker.commands[0]
    assert create[create.index("--add-host") + 1] == "model-server:10.9.0.2"
    assert create[create.index("--dns") + 1] == "127.0.0.1"


def test_the_host_config_names_builds_and_the_models_directory(tmp_path):
    from silverquillm.host_config import HostConfigError, load_host_config

    path = tmp_path / "config.toml"
    path.write_text(
        '[model_server]\nmodels_dir = "models"\n'
        '[model_server.llama_cpp]\nb12182 = "/opt/llama/b12182/llama-server"\n'
    )
    config = load_host_config(path)
    assert config.models_dir == tmp_path / "models"
    assert config.llama_cpp == {"b12182": Path("/opt/llama/b12182/llama-server")}
    path.write_text('[model_server.llama_cpp]\nlatest = "/opt/llama-server"\n')
    with pytest.raises(HostConfigError, match="maps builds like b12182"):
        load_host_config(path)
    path.write_text('[model_server]\nbinary = "/opt/llama-server"\n')
    with pytest.raises(HostConfigError, match="takes only models_dir and llama_cpp"):
        load_host_config(path)


def test_a_body_larger_than_one_read_reaches_the_relay_whole(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    with ModelRelayCollector(tmp_path / "run", plan=plan) as collector:
        forward = ModelForwardServer(("127.0.0.1", 0), collector.endpoint)
        thread = threading.Thread(target=forward.serve_forever, daemon=True)
        thread.start()
        try:
            long_history = [{"role": "user", "content": "x" * 4_000_000}]
            status, body = post(
                f"http://127.0.0.1:{forward.server_address[1]}/v1/chat/completions",
                {"stream": True, "messages": long_history},
            )
            assert status == 200 and b'"usage"' in body
        finally:
            forward.shutdown()
            forward.server_close()
            thread.join()
        assert len(collector.finalize(exit_kind="completed")["requests"]) == 1
