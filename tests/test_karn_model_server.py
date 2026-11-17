"""The local model server (issues #262, #271), against a fake llama-server."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from silverquillm.karn.definition import KarnError
from silverquillm.karn.docker import Network
from silverquillm.karn.model_server import (
    MODEL_SERVER_ENV,
    MODEL_SERVER_URL,
    GpuReading,
    ModelRelayCollector,
    ModelServerBusyError,
    ModelServerHost,
    claim_gpu_slot,
    claim_model_server,
    file_sha256,
    gpu_slot_availability,
    gpu_slots,
    model_server_spec,
    plan_model_server,
    read_gpus,
    server_environment,
    summarize_model_events,
)
from silverquillm.karn.observations import summarize_events
from silverquillm.karn.proxy import ModelForwardServer

FAKE_SERVER = r"""
import json, os, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
if "--version" in sys.argv:
    with open(sys.argv[0] + ".version-env", "w") as out:
        json.dump(dict(os.environ), out)
    print("version: 0.9.0-dev (build 12182, commit fd27b2034)")
    sys.exit(0)
port = int(sys.argv[sys.argv.index("--port") + 1])
alias = sys.argv[sys.argv.index("--alias") + 1]
with open(sys.argv[0] + ".argv", "w") as out:
    json.dump(sys.argv[1:], out)
with open(sys.argv[0] + ".env", "w") as out:
    json.dump(dict(os.environ), out)

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
    def hold(self):
        # A request still in prompt processing: say so, then wait to be released.
        open(sys.argv[0] + ".held", "a").write("1")
        for _ in range(600):
            if os.path.exists(sys.argv[0] + ".release"):
                return
            time.sleep(0.05)
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        messages = request.get("messages")
        last = messages[-1].get("content") if isinstance(messages, list) and messages else None
        if last == "hold":
            self.hold()
        if isinstance(last, str) and last.startswith("delay:"):
            time.sleep(float(last[len("delay:"):]))
        if last == "hold-close":
            # A close-delimited stream, which http.client reads after dropping its socket.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"data: {}\n\n")
            self.wfile.flush()
            self.hold()
            return
        if last in ("eof-stream", "eof-after-finish"):
            # The server closes a stream early, before or after its final choice.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            choice = {"index": 0, "delta": {"content": "partial"}}
            if last == "eof-after-finish":
                choice["finish_reason"] = "stop"
            self.wfile.write(b"data: " + json.dumps({"id": "chatcmpl-1", "model": alias,
                "choices": [choice]}).encode() + b"\n\n")
            self.close_connection = True
            return
        if last in ("truncated", "malformed"):
            body = b'{"id": "chatcmpl-1", "choices": ['
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body) + (100 if last == "truncated" else 0)))
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True
            return
        usage = {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
                 "prompt_tokens_details": {"cached_tokens": 60}}
        if last == "no-usage":
            usage = None
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
        for position, chunk in enumerate(
            [*(b"data: " + json.dumps(c).encode() + b"\n\n" for c in chunks), b"data: [DONE]\n\n"]
        ):
            if position == 1 and last == "hold-stream":
                self.wfile.flush()
                self.hold()
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


@pytest.fixture(autouse=True)
def no_gpus(monkeypatch):
    """Runs never ask this machine's ``nvidia-smi``; a test that wants GPUs sets them."""
    from silverquillm.karn import model_server

    reading = GpuReading(None, reason="nvidia_smi_unavailable")
    monkeypatch.setattr(model_server, "read_gpus", lambda: reading)
    return reading


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
        (spec_document(arguments=["--host=0.0.0.0"]), "flag_not_allowed:--host"),
        (spec_document(arguments=["-hf", "org/model"]), "flag_not_allowed:-hf"),
        (spec_document(arguments=["--rpc", "10.0.0.2:50052"]), "flag_not_allowed:--rpc"),
        (spec_document(arguments=["--log-file", "/tmp/x"]), "flag_not_allowed:--log-file"),
        (spec_document(arguments=["--media-path", "/"]), "flag_not_allowed:--media-path"),
        (spec_document(arguments=["--tools", "all"]), "flag_not_allowed:--tools"),
        *(
            (spec_document(arguments=[flag]), "flag_not_allowed:" + flag)
            for flag in (
                *("-ag", "--agent", "--connect", "--embd-gemma-default", "--fim-qwen-1.5b-default"),
                *("--fim-qwen-3b-default", "--fim-qwen-7b-default", "--fim-qwen-7b-spec"),
                *("--fim-qwen-14b-spec", "--fim-qwen-30b-default", "--gpt-oss-20b-default"),
                *("--gpt-oss-120b-default", "--vision-gemma-4b-default", "-f", "-bf"),
                "--vision-gemma-12b-default",
            )
        ),
        (spec_document(arguments=["-md", "draft.gguf"]), "flag_not_allowed:-md"),
        (spec_document(arguments=["--chat-template-file=t.jinja"]), "flag_not_allowed:--chat"),
        (spec_document(arguments=["-c", "8\0"]), "model_server_arguments_invalid"),
        ({**spec_document(), "files": []}, "model_server_spec_invalid"),
        ({**spec_document(), "extra": 1}, "model_server_spec_invalid"),
    ],
)
def test_a_malformed_server_is_refused(document, reason):
    with pytest.raises(KarnError, match=reason):
        model_server_spec(runtime(document))


def test_any_agent_variable_may_point_at_the_relay_on_a_restricted_network():
    environment = runtime()["environment"]
    del environment["CONSTRUCT_PI_BASE_URL"]
    agent = {"environment": {**environment, "OPENAI_BASE_URL": MODEL_SERVER_URL}}
    assert model_server_spec({**agent, "network": {"mode": "restricted"}}) is not None
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
    assert measurements["subagents"] is None and measurements["subagent_threads"] is None
    assert measurements["subagents_reason"] == "threads_not_observable"
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


def gpu(index, *, used=14, uuid=None):
    return {
        "index": index,
        "uuid": uuid or f"GPU-{index}",
        "name": "NVIDIA H100 80GB HBM3",
        "memory_total_mib": 81559,
        "memory_used_mib": used,
        "power_limit_w": 700,
        "driver_version": "580.1",
    }


def h100s(*, used=None, compute=()):
    used = used or {}
    return GpuReading(
        tuple(gpu(index, used=used.get(index, 14)) for index in range(4)),
        frozenset(f"GPU-{index}" for index in compute),
    )


def test_a_host_without_gpu_slots_serves_one_run_at_a_time_on_the_runners_gpus(tmp_path):
    (slot,) = gpu_slots(tmp_path, None)
    assert slot.value is None and slot.lock_path == tmp_path.resolve() / "model-server.lock"
    runner = {"CUDA_VISIBLE_DEVICES": "1", "CUDA_DEVICE_ORDER": "FASTEST_FIRST"}
    # No busy check: a desktop's own display may hold more than 1 GiB.
    busy = h100s(used={0: 8000, 1: 8000}, compute=[0, 1])
    claim = claim_gpu_slot((slot,), lambda: busy, runner)
    assert claim.facts() == {
        "gpu_slot": None,
        "cuda_visible_devices": "1",
        "cuda_device_order": "FASTEST_FIRST",
        "gpus": [gpu(index, used=busy.gpus[index]["memory_used_mib"]) for index in range(4)],
    }
    with pytest.raises(ModelServerBusyError, match="model_server_busy"):
        claim_gpu_slot((slot,), h100s, runner)
    claim.release()
    claim_gpu_slot((slot,), h100s, runner).release()


@pytest.mark.parametrize(
    ("runner", "selection"),
    [
        (
            {"CUDA_VISIBLE_DEVICES": "2,0", "CUDA_DEVICE_ORDER": "FASTEST_FIRST"},
            ("2,0", "FASTEST_FIRST"),
        ),
        ({"CUDA_VISIBLE_DEVICES": "", "CUDA_DEVICE_ORDER": "PCI_BUS_ID"}, ("", "PCI_BUS_ID")),
        ({}, (None, None)),
    ],
    ids=["restricted", "empty", "unset"],
)
def test_without_gpu_slots_the_runners_selection_passes_exactly_as_set(
    served, tmp_path, runner, selection
):
    plan = plan_model_server(served.spec, served.host, served.state)
    claimed = claim_model_server(plan, inherited=runner)
    host = claimed.to_dict()["host"]
    assert (host["cuda_visible_devices"], host["cuda_device_order"]) == selection
    environment = server_environment(
        served.spec, {}, tmp_path, {"PATH": "/bin", **runner}, gpu=claimed.claim.environment
    )
    for name, value in zip(("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER"), selection, strict=True):
        assert environment.get(name) == value
    claimed.claim.release()


def test_each_run_claims_the_first_free_gpu_slot_and_its_lock_is_named_by_its_value(tmp_path):
    slots = gpu_slots(tmp_path, ("0", "1", "2"))
    assert [slot.lock_path.name for slot in slots] == [
        "model-server-gpu-0.lock",
        "model-server-gpu-1.lock",
        "model-server-gpu-2.lock",
    ]
    first, second = (claim_gpu_slot(slots, h100s) for _ in range(2))
    assert (first.slot.value, second.slot.value) == ("0", "1")
    assert second.facts() == {
        "gpu_slot": "1",
        "cuda_visible_devices": "1",
        "cuda_device_order": "PCI_BUS_ID",
        "gpus": [gpu(1)],
    }
    reordered = gpu_slots(tmp_path, ("1", "0", "2"))
    assert claim_gpu_slot(reordered, h100s).slot.value == "2"


@pytest.mark.parametrize(
    "reading",
    [h100s(compute=[0]), h100s(used={0: 2048})],
    ids=["another-users-process", "memory-in-use-with-no-process-listed"],
)
def test_a_gpu_another_job_is_using_keeps_its_slot_busy_whatever_its_lock(tmp_path, reading):
    slots = gpu_slots(tmp_path, ("0", "1"))
    assert claim_gpu_slot(slots, lambda: reading).slot.value == "1"
    with pytest.raises(ModelServerBusyError):
        claim_gpu_slot(gpu_slots(tmp_path, ("0",)), lambda: reading)


def test_without_nvidia_smi_only_the_lock_decides_and_the_gpus_are_unknown(tmp_path):
    slots = gpu_slots(tmp_path, ("0", "1"))
    unread = GpuReading(None, reason="nvidia_smi_unavailable")
    claim = claim_gpu_slot(slots, lambda: unread)
    assert claim.facts() == {
        "gpu_slot": "0",
        "cuda_visible_devices": "0",
        "cuda_device_order": "PCI_BUS_ID",
        "gpus": None,
        "gpus_reason": "nvidia_smi_unavailable",
    }


def test_a_gpu_slot_naming_a_gpu_nvidia_smi_does_not_list_refuses_the_run(tmp_path):
    two = GpuReading((gpu(0), gpu(1)))
    with pytest.raises(KarnError, match="gpu_slot_unknown_gpu:7"):
        claim_gpu_slot(gpu_slots(tmp_path, ("0", "7")), lambda: two)
    with pytest.raises(KarnError, match="gpu_slot_unknown_gpu:1,2"):
        claim_gpu_slot(gpu_slots(tmp_path, ("1,2",)), lambda: two)
    # Unread, the slot cannot be judged, and only its lock decides.
    claim_gpu_slot(gpu_slots(tmp_path, ("7",)), lambda: GpuReading(None)).release()


def test_an_unusable_lock_file_skips_its_slot_and_defers_rather_than_failing(tmp_path):
    slots = gpu_slots(tmp_path, ("0", "1"))
    claim_gpu_slot(slots, h100s).release()
    claim_gpu_slot(slots[1:], h100s).release()
    slots[0].lock_path.chmod(0)
    try:
        claim = claim_gpu_slot(slots, h100s)
        assert claim.slot.value == "1"
        with pytest.raises(ModelServerBusyError) as refused:
            claim_gpu_slot(slots, h100s)
        assert refused.value.unusable and str(slots[0].lock_path) in refused.value.unusable[0]
        claim.release()
        claimable, unusable = gpu_slot_availability(slots, h100s)
        assert claimable and len(unusable) == 1
        slots[1].lock_path.chmod(0)
        assert gpu_slot_availability(slots, h100s) == (
            False,
            unusable + (f"{slots[1].lock_path}: Permission denied",),
        )
    finally:
        for slot in slots:
            slot.lock_path.chmod(0o600)


def test_the_schedulers_probe_reads_the_lock_table_and_never_takes_a_lock(tmp_path):
    slots = gpu_slots(tmp_path, ("0",))
    claim_gpu_slot(slots, h100s).release()
    table = tmp_path / "proc-locks"
    table.write_text("")
    probes = []

    def flock(*args):
        probes.append(args)
        raise AssertionError("the probe took a lock")

    import fcntl

    original = fcntl.flock
    fcntl.flock = flock
    try:
        assert gpu_slot_availability(slots, h100s, locks=table) == (True, ())
    finally:
        fcntl.flock = original
    held = claim_gpu_slot(slots, h100s)
    table.write_text(Path("/proc/locks").read_text())
    assert gpu_slot_availability(slots, h100s, locks=table) == (False, ())
    held.release()
    # A host without GPU Slots never asks nvidia-smi to judge its one lock.
    unpinned = gpu_slots(tmp_path / "unpinned", None)

    def unexpected():
        raise AssertionError("nvidia-smi read for a host without GPU Slots")

    assert gpu_slot_availability(unpinned, unexpected, locks=table) == (True, ())


def smi_output(gpus: bytes, apps: bytes = b"", code: int = 0):
    def run(argv):
        assert "--format=csv,noheader,nounits" in argv
        return code, gpus if argv[1].startswith("--query-gpu=") else apps

    return run


def test_nvidia_smi_is_read_into_facts_and_its_failures_into_reasons():
    reading = read_gpus(
        smi_output(
            b"0, GPU-a, NVIDIA GeForce RTX 3090, 5, 24576, 240.00, 595.91.07\n\n"
            b"1, GPU-b, NVIDIA GeForce RTX 3090, 3000, 24576, [N/A], 595.91.07\n",
            b"\nGPU-b, 4242, 2990\n",
        )
    )
    assert reading.reason is None and reading.compute_uuids == {"GPU-b"}
    assert reading.gpus[0] == {
        "index": 0,
        "uuid": "GPU-a",
        "name": "NVIDIA GeForce RTX 3090",
        "memory_total_mib": 24576,
        "memory_used_mib": 5,
        "power_limit_w": 240,
        "driver_version": "595.91.07",
    }
    assert reading.gpus[1]["power_limit_w"] is None

    def missing(argv):
        raise FileNotFoundError(argv[0])

    def hangs(argv):
        raise subprocess.TimeoutExpired(argv, 10)

    assert read_gpus(missing) == GpuReading(None, reason="nvidia_smi_unavailable")
    assert read_gpus(hangs) == GpuReading(None, reason="nvidia_smi_unavailable")
    assert read_gpus(smi_output(b"", code=9)).reason == "nvidia_smi_failed"
    for output in (
        b"garbage\n",
        b"\xff\xfe, GPU-a, x, 5, 24576, 240, 1\n",
        b"0, GPU-a, x, nan, 24576, 240, 1\n",
        b"0, GPU-a, x, 5, inf, 240, 1\n",
        "\u00b2, GPU-a, x, 5, 24576, 240, 1\n".encode(),
    ):
        assert read_gpus(smi_output(output)).reason == "nvidia_smi_unreadable", output


def test_a_stuck_nvidia_smi_is_abandoned_within_its_bound(tmp_path, monkeypatch):
    from silverquillm.karn import model_server

    stuck = tmp_path / "nvidia-smi"
    stuck.write_text("#!/bin/sh\nexec sleep 30\n")
    stuck.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setattr(model_server, "NVIDIA_SMI_SECONDS", 0.5)
    started = time.monotonic()
    reading = read_gpus()
    assert reading == GpuReading(None, reason="nvidia_smi_unavailable")
    assert time.monotonic() - started < 5


def test_with_gpu_slots_the_slots_selection_overrides_the_runners(served, tmp_path):
    runner = {
        "PATH": "/bin",
        "CUDA_VISIBLE_DEVICES": "0,1,2,3",
        "CUDA_DEVICE_ORDER": "FASTEST_FIRST",
    }
    runner |= {"LLAMA_ARG_CTX_SIZE": "4096", "LD_LIBRARY_PATH": "/opt/old"}
    pinned = ModelServerHost(served.host.models_dir, served.host.llama_cpp, {}, ("0", "1"))
    plan = plan_model_server(served.spec, pinned, served.state)
    claimed = [claim_model_server(plan, h100s, runner) for _ in range(2)]
    environment = server_environment(
        served.spec, {}, tmp_path, runner, gpu=claimed[1].claim.environment
    )
    assert environment["CUDA_VISIBLE_DEVICES"] == "1"
    assert environment["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    assert "LLAMA_ARG_CTX_SIZE" not in environment and "LD_LIBRARY_PATH" not in environment
    unpinned = server_environment(served.spec, {}, tmp_path, runner)
    assert unpinned["CUDA_VISIBLE_DEVICES"] == "0,1,2,3"
    assert "LLAMA_ARG_CTX_SIZE" not in unpinned and "LD_LIBRARY_PATH" not in unpinned
    host = claimed[1].to_dict()["host"]
    assert host["gpu_slot"] == "1" and host["gpus"] == [gpu(1)]
    assert host["binary_sha256"] == hashlib.sha256(served.binary.read_bytes()).hexdigest()
    with ModelRelayCollector(tmp_path / "run", plan=claimed[1]):
        served_environment = json.loads(Path(str(served.binary) + ".env").read_text())
    assert served_environment["CUDA_VISIBLE_DEVICES"] == "1"
    assert served_environment["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"


def test_the_collector_releases_its_gpu_slot_once_the_server_stops(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    claimed = claim_model_server(plan)
    with ModelRelayCollector(tmp_path / "run", plan=claimed) as collector:
        with pytest.raises(ModelServerBusyError):
            claim_model_server(plan)
        assert collector.facts["host"]["gpu_slot"] is None
    claim_model_server(plan).claim.release()


def test_a_server_that_outlives_its_stop_keeps_its_gpu_slot_held(served, tmp_path, monkeypatch):
    from silverquillm.karn import model_server

    plan = plan_model_server(served.spec, served.host, served.state)
    claimed = claim_model_server(plan)

    def stuck_exit(self, *_):
        raise subprocess.TimeoutExpired("llama-server", 30)

    monkeypatch.setattr(model_server.LlamaServer, "__exit__", stuck_exit)
    collector = ModelRelayCollector(tmp_path / "run", plan=claimed)
    with pytest.raises(subprocess.TimeoutExpired), collector:
        pass
    with pytest.raises(ModelServerBusyError):
        claim_model_server(plan)
    claimed.claim.release()
    with pytest.raises(ModelServerBusyError):
        claim_model_server(plan)
    collector.llama.process.kill()
    collector.llama.process.wait()


def pinned_run(served, tmp_path, slots):
    opts = model_server_run(served, tmp_path)
    opts["model_server_host"] = ModelServerHost(
        served.host.models_dir, served.host.llama_cpp, {}, slots
    )
    return opts


def test_a_direct_run_with_no_free_gpu_slot_is_refused_before_any_evidence(served, tmp_path):
    from silverquillm.karn.execution import run_benchmark

    opts = pinned_run(served, tmp_path, ("0",))
    held = claim_model_server(
        plan_model_server(served.spec, opts["model_server_host"], opts["state_root"])
    )
    launched = []
    with pytest.raises(ModelServerBusyError, match="model_server_busy"):
        run_benchmark(**opts, run_id="refused", on_launch=lambda: launched.append(1))
    assert not launched and not (opts["results_dir"] / "refused").exists()
    held.claim.release()


def test_a_run_holds_its_gpu_slot_from_before_launch_until_its_server_stops(served, tmp_path):
    from silverquillm.karn.execution import run_benchmark

    opts = pinned_run(served, tmp_path, ("0", "1"))
    plan = plan_model_server(served.spec, opts["model_server_host"], opts["state_root"])
    selected, at_launch, at_grading = [], [], []

    def probe():
        claim = claim_model_server(plan)
        claim.claim.release()
        return claim.claim.slot.value

    evaluate = opts["grader"].evaluate_run

    def evaluator(*args, **kwargs):
        at_grading.append(probe())
        return evaluate(*args, **kwargs)

    record = run_benchmark(
        **opts,
        run_id="pinned",
        on_gpu_slot_selected=selected.append,
        on_launch=lambda: at_launch.append(probe()),
        evaluator=evaluator,
    )
    assert selected == ["0"] and at_launch == ["1"] and at_grading == ["0"]
    host = record.run_metadata["model_server"]["host"]
    assert host["gpu_slot"] == "0"
    assert host["gpus"] is None and host["gpus_reason"] == "nvidia_smi_unavailable"
    run_input = json.loads((opts["results_dir"] / "pinned" / "run-input.json").read_text())
    assert run_input["model_server"]["host"] == host


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
        stdout = b""
        if args[:2] == ("network", "inspect"):
            stdout = json.dumps([{"IPAM": {"Config": [{"Subnet": "10.9.0.0/24"}]}}]).encode()
        return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")

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
        runtime = create.index("--runtime")
        assert create[runtime + 1] == "runc" and runtime < create.index("sha256:" + "1" * 64)
        assert "SILVERQUILLM_MODEL_ENDPOINT=http://h:1/model/x" in create
        assert "SILVERQUILLM_MODEL_CLIENTS=10.9.0.0/24" in create
        assert "SILVERQUILLM_MODEL_TIMEOUT=1800" in create
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
    with pytest.raises(HostConfigError, match="takes only models_dir, llama_cpp, environment"):
        load_host_config(path)


@pytest.mark.parametrize(
    "name", ["GGML_VK_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES"]
)
def test_only_the_gpu_selection_chooses_gpus(name):
    from silverquillm.karn.model_server import environment_refusal

    assert environment_refusal({name: "0"}) == "refused:" + name
    assert environment_refusal({name: "0"}, host=True) == "refused:" + name


def test_the_host_config_lists_gpu_slots_that_never_share_a_gpu(tmp_path):
    from silverquillm.host_config import load_host_config

    path = tmp_path / "config.toml"
    assert load_host_config(path).gpu_slots is None
    path.write_text('[model_server]\ngpu_slots = ["0", "1", "2,3"]\n')
    assert load_host_config(path).gpu_slots == ("0", "1", "2,3")


@pytest.mark.parametrize(
    ("slots", "reason"),
    [
        ('["0", "0,1"]', "may not name a GPU twice"),
        ('["1", "1"]', "may not name a GPU twice"),
        ('["0,0"]', "may not name a GPU twice"),
        ("[]", "non-empty list"),
        ('"0"', "non-empty list"),
        ('["0, 1"]', "GPU indices"),
        ('["01"]', "GPU indices"),
        ('["GPU-abc"]', "GPU indices"),
        ('["\u00b2"]', "GPU indices"),
        ('["\u0661"]', "GPU indices"),
        ('[""]', "GPU indices"),
        ("[0]", "GPU indices"),
    ],
)
def test_gpu_slots_that_would_share_or_misname_a_gpu_are_refused(tmp_path, slots, reason):
    from silverquillm.host_config import HostConfigError, load_host_config

    path = tmp_path / "config.toml"
    path.write_text(f"[model_server]\ngpu_slots = {slots}\n")
    with pytest.raises(HostConfigError, match=reason):
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


def test_the_sidecar_serves_only_its_own_runs_network(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    with ModelRelayCollector(tmp_path / "run", plan=plan) as collector:
        forward = ModelForwardServer(("127.0.0.1", 0), collector.endpoint, "10.9.0.0/24")
        thread = threading.Thread(target=forward.serve_forever, daemon=True)
        thread.start()
        try:
            with socket.create_connection(forward.server_address, timeout=5) as client:
                client.sendall(b"GET /v1/models HTTP/1.1\r\n\r\n")
                assert client.recv(4096) == b""
        finally:
            forward.shutdown()
            forward.server_close()
            thread.join()
        assert collector.finalize(exit_kind="completed")["coverage"]["relayed_requests"] == 0


def test_workload_content_is_kept_bounded_and_overrides_are_recorded(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        post(
            collector.endpoint + "/v1/chat/completions",
            {
                "model": "m" * 100_000,
                "temperature": 0,
                "messages": [{"role": "user", "content": "x" * 2_000_000}],
            },
        )
        with pytest.raises(urllib.error.HTTPError) as refused:
            post(collector.endpoint + "/v1/chat/completions", {"n": 4, "messages": []})
        assert refused.value.code == 400
        post(collector.endpoint + "/v1/chat/completions", {"messages": 5})
        measurements = collector.finalize(exit_kind="completed")
    start, event, _, malformed = collector.events
    assert start["kind"] == "request_started" and start["id"] == event["id"]
    assert start["requested_model"]["truncated_from_chars"] == 100_002
    assert event["requested_model"]["truncated_from_chars"] == 100_002
    assert event["request_parameters"] == {"temperature": 0}
    assert malformed["request_messages"] is None and malformed["status"] == 200
    assert (run_dir / "observations.events.jsonl").stat().st_size < 20_000
    kept = json.loads((run_dir / "model-transcript.jsonl").open().readline())["new_messages"]
    assert len(kept["head"]) == 1024 * 1024
    assert measurements["coverage"]["requests_with_parameter_overrides"] == 1


def test_split_models_are_refused_since_only_one_file_is_verified():
    document = spec_document(model={"file": "Qwen-BF16-00001-of-00002.gguf", "sha256": "0" * 64})
    with pytest.raises(KarnError, match="model_server_model_invalid"):
        model_server_spec(runtime(document))


def test_lost_or_repeated_usage_leaves_usage_partial():
    base = {"kind": "response", "status": 200, "model": "m", "timestamp_ms": 1, "tool_calls": 0}
    usage = {
        key: 1
        for key in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "total_tokens",
            "reasoning_output_tokens",
        )
    }
    usage["cache_write_input_tokens"] = 0
    lost = [
        {**base, "id": "a", "response_id": "a", "usage": usage},
        {**base, "id": "b", "response_id": "b", "usage": None, "error": "client_disconnected"},
    ]
    reasons = summarize_model_events(lost, exit_kind="completed")["usage"]["reasons"]
    assert reasons == ["relayed_request_incomplete"]
    repeated = [{**base, "id": "a", "response_id": "a", "usage": usage, "usage_reports": 4}]
    reasons = summarize_model_events(repeated, exit_kind="completed")["usage"]["reasons"]
    assert reasons == ["multiple_usage_reports"]


def held(served, count=1):
    marker = Path(str(served.binary) + ".held")
    for _ in range(200):
        if marker.exists() and len(marker.read_text()) >= count:
            return
        time.sleep(0.05)
    raise AssertionError("the fake server never held a request")


def in_background(url, content, *, stream=True):
    outcome = {}

    def send():
        try:
            outcome["status"] = post(
                url, {"stream": stream, "messages": [{"role": "user", "content": content}]}
            )[0]
        except Exception as error:  # noqa: BLE001 -- the client only reports what it saw.
            outcome["error"] = type(error).__name__

    thread = threading.Thread(target=send, daemon=True)
    thread.start()
    return thread, outcome


def replayed(run_dir, exit_kind):
    events = [json.loads(line) for line in (run_dir / "observations.events.jsonl").open()]
    return events, summarize_events(events, exit_kind=exit_kind, adapter="model_server")


def test_a_request_without_its_first_byte_at_finalize_is_cancelled_and_counted(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        in_background(collector.endpoint + "/v1/chat/completions", "hold")
        held(served)
        started = time.monotonic()
        measurements = collector.finalize(exit_kind="deadline")
        assert time.monotonic() - started < 5
        Path(str(served.binary) + ".release").write_text("")
        time.sleep(0.3)
    assert measurements["coverage"]["relayed_requests"] == 1
    assert measurements["coverage"]["failed_requests"] == 1
    assert "relayed_request_incomplete" in measurements["usage"]["reasons"]
    events, replay = replayed(run_dir, "deadline")
    assert [event["kind"] for event in events] == ["request_started", "response"]
    assert events[1]["error"] == "cancelled_at_finalize"
    assert replay["coverage"] == measurements["coverage"]
    assert replay["usage"] == measurements["usage"]


def test_a_stream_cut_mid_response_is_never_counted_complete(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        in_background(collector.endpoint + "/v1/chat/completions", "hold-stream")
        held(served)
        measurements = collector.finalize(exit_kind="deadline")
    assert measurements["requests"] == []
    assert measurements["coverage"]["failed_requests"] == 1
    events, replay = replayed(run_dir, "deadline")
    assert events[-1]["status"] == 200 and events[-1]["error"] == "cancelled_at_finalize"
    assert replay["coverage"] == measurements["coverage"]


def test_concurrent_requests_settle_once_each_at_finalize(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        url = collector.endpoint + "/v1/chat/completions"
        assert post(url, {"messages": [{"role": "user", "content": "done"}]})[0] == 200
        in_background(url, "hold")
        in_background(url, "hold-stream")
        held(served, 2)
        measurements = collector.finalize(exit_kind="deadline")
        assert collector.finalize(exit_kind="deadline")["coverage"] == measurements["coverage"]
    assert measurements["coverage"]["relayed_requests"] == 3
    assert measurements["coverage"]["failed_requests"] == 2
    assert len(measurements["requests"]) == 1
    events, replay = replayed(run_dir, "deadline")
    assert sum(event["kind"] == "response" for event in events) == 3
    assert replay["coverage"] == measurements["coverage"]
    assert replay["requests"] == measurements["requests"]


def test_a_request_finishing_as_the_run_ends_is_counted_once(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        thread, _ = in_background(collector.endpoint + "/v1/chat/completions", "hold")
        held(served)
        Path(str(served.binary) + ".release").write_text("")
        measurements = collector.finalize(exit_kind="completed")
        thread.join(5)
    assert measurements["coverage"]["relayed_requests"] == 1
    events, replay = replayed(run_dir, "completed")
    assert sum(event["kind"] == "response" for event in events) == 1
    assert replay["coverage"] == measurements["coverage"]
    assert replay["requests"] == measurements["requests"]


def test_a_start_with_no_terminal_record_is_unfinished_for_recovery():
    events = [
        {"id": "a", "kind": "request_started", "timestamp_ms": 1},
        {
            "id": "a",
            "kind": "response",
            "response_id": "x",
            "status": 200,
            "model": "m",
            "usage": None,
            "timestamp_ms": 1,
            "tool_calls": 0,
        },
        {"id": "b", "kind": "request_started", "timestamp_ms": 2},
        {"id": "b", "kind": "request_started", "timestamp_ms": 2},
    ]
    measurements = summarize_model_events(events, exit_kind="interrupted")
    assert measurements["coverage"]["relayed_requests"] == 2
    assert measurements["coverage"]["failed_requests"] == 1
    assert measurements["coverage"]["unfinished_requests"] == 1
    assert len(measurements["requests"]) == 1
    assert "relayed_request_incomplete" in measurements["usage"]["reasons"]


class RelayHost:
    """A workload that asks the run's model server one question and stops."""

    def __init__(self):
        from .test_karn_execution import FixtureHost

        self.inner = FixtureHost()
        self.docker = self.inner.docker

    def preflight(self, candidate, budget_seconds):
        pass

    def run(self, candidate, workspace, evidence_dir, prompt, *, model_endpoint, **kwargs):
        post(
            model_endpoint + "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "go"}]},
        )
        return self.inner.run(candidate, workspace, evidence_dir, prompt, **kwargs)


def model_server_run(served, tmp_path):
    from .test_karn_execution import options
    from .test_karn_host import make_candidate

    document = spec_document(model={"file": "model.gguf", "sha256": served.spec.model_sha256})
    candidate = make_candidate(
        tmp_path / "recipe",
        network={"mode": "restricted", "https_hosts": []},
        environment={
            "CONSTRUCT_MODEL": "qwen3.8-27b",
            "CONSTRUCT_PI_BASE_URL": MODEL_SERVER_URL,
            MODEL_SERVER_ENV: json.dumps(document),
        },
    )
    return options(
        tmp_path,
        build_output=candidate.build_output,
        host=RelayHost(),
        model_server_host=served.host,
        collector_host="127.0.0.1",
    )


def interrupted_run(opts, run_id):
    from silverquillm.karn.execution import run_benchmark

    def runner_dies(*args, **kwargs):
        raise SystemExit(91)

    with pytest.raises(SystemExit):
        run_benchmark(**opts, run_id=run_id, evaluator=runner_dies)
    return opts["results_dir"] / run_id


def recover(opts, run_id, monkeypatch, tmp_path):
    from silverquillm.karn import recovery

    docker = SimpleNamespace(stop_and_confirm=lambda *args: None, cleanup_run=lambda *args: None)
    monkeypatch.setattr(
        recovery,
        "DockerHost",
        lambda **kwargs: SimpleNamespace(docker=docker, plugin_cache=tmp_path / "cache"),
    )
    keys = ("bench_root", "results_dir", "results_repo", "state_root", "grader")
    return recovery.recover_benchmark(run_id=run_id, spec={}, **{key: opts[key] for key in keys})


def test_recovery_keeps_the_server_the_run_verified_without_reverifying(
    served, tmp_path, monkeypatch
):
    opts = model_server_run(served, tmp_path)
    run_dir = interrupted_run(opts, "cut")
    inputs = json.loads((run_dir / "run-input.json").read_text())
    assert inputs["model_server"]["model_sha256_verified"] is True
    # The host's files are gone by the time the run is recovered; recovery never reads them.
    served.binary.unlink()
    (served.host.models_dir / "model.gguf").unlink()
    recovered = recover(opts, "cut", monkeypatch, tmp_path)
    server = recovered.run_metadata["model_server"]
    assert server == inputs["model_server"]
    assert server["model"]["sha256"] == served.spec.model_sha256
    assert server["model_bytes"] == len(b"GGUF weights")
    assert recovered.run_metadata["native_telemetry"]["adapter"] == "model_server"
    measurements = recovered.run_metadata["measurements"]
    assert measurements["coverage"]["relayed_requests"] == 1
    assert measurements["requests"][0]["model"] == "qwen3.8-27b"


def test_a_recovered_record_keeps_the_gpu_selection_its_run_recorded(served, tmp_path, monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "1")
    monkeypatch.setenv("CUDA_DEVICE_ORDER", "FASTEST_FIRST")
    opts = model_server_run(served, tmp_path)
    interrupted_run(opts, "selected")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    monkeypatch.delenv("CUDA_DEVICE_ORDER")
    recovered = recover(opts, "selected", monkeypatch, tmp_path)
    host = recovered.run_metadata["model_server"]["host"]
    assert (host["gpu_slot"], host["cuda_visible_devices"], host["cuda_device_order"]) == (
        None,
        "1",
        "FASTEST_FIRST",
    )
    assert host["gpus"] is None and host["gpus_reason"] == "nvidia_smi_unavailable"


def test_a_run_that_failed_before_verifying_recovers_with_verification_unknown(
    served, tmp_path, monkeypatch
):
    from silverquillm.karn import model_server

    opts = model_server_run(served, tmp_path)

    def runner_dies(path):
        raise SystemExit(91)

    with monkeypatch.context() as patch:
        patch.setattr(model_server, "file_sha256", runner_dies)
        with pytest.raises(SystemExit):
            from silverquillm.karn.execution import run_benchmark

            run_benchmark(**opts, run_id="unverified")
    recovered = recover(opts, "unverified", monkeypatch, tmp_path)
    server = recovered.run_metadata["model_server"]
    assert server["model_sha256_verified"] is None
    assert server["model"]["sha256"] == served.spec.model_sha256
    assert "model_bytes" not in server
    assert recovered.run_metadata["measurements"]["coverage"]["relayed_requests"] == 0


def test_a_changed_model_file_is_recorded_unverified_and_never_served(served, tmp_path):
    from silverquillm.karn.execution import run_benchmark

    opts = model_server_run(served, tmp_path)
    (served.host.models_dir / "model.gguf").write_bytes(b"other weights")
    record = run_benchmark(**opts, run_id="changed")
    assert record.run_metadata["model_server"]["model_sha256_verified"] is None
    assert record.run_metadata["execution"]["error"] == "model_digest_mismatch"


def test_a_close_delimited_stream_is_cancelled_without_waiting(served, tmp_path):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        in_background(collector.endpoint + "/v1/chat/completions", "hold-close")
        held(served)
        started = time.monotonic()
        measurements = collector.finalize(exit_kind="deadline")
        assert time.monotonic() - started < 5
    events, replay = replayed(run_dir, "deadline")
    assert events[-1]["error"] == "cancelled_at_finalize"
    assert measurements["coverage"]["unfinished_requests"] == 0
    assert replay["coverage"] == measurements["coverage"]


def failing_writes(monkeypatch, sink, plan):
    """Makes the next appends to ``sink`` go as ``plan`` says: None writes, "error" writes
    nothing and fails, "partial" writes half the line and then fails."""
    from silverquillm.karn import model_server

    real, plan = model_server.os.write, list(plan)

    def write(fd, data):
        if fd != sink.fd or not plan or (step := plan.pop(0)) is None:
            return real(fd, data)
        if step == "partial":
            plan.insert(0, "error")
            return real(fd, bytes(data[: len(data) // 2]))
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(model_server.os, "write", write)


def test_a_start_that_cannot_be_written_is_refused_not_relayed(served, tmp_path, monkeypatch):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        failing_writes(monkeypatch, collector._sink, ["error"])
        with pytest.raises(urllib.error.HTTPError) as refused:
            post(collector.endpoint + "/v1/chat/completions", {"messages": []})
        assert refused.value.code == 503
        started = time.monotonic()
        measurements = collector.finalize(exit_kind="completed")
        assert time.monotonic() - started < 5
    assert measurements["coverage"]["relayed_requests"] == 0
    assert not Path(str(served.binary) + ".held").exists()


def ask(collector, content, *, stream=True):
    return post(
        collector.endpoint + "/v1/chat/completions",
        {"stream": stream, "messages": [{"role": "user", "content": content}]},
    )


def assert_replay_agrees(run_dir, measurements, exit_kind="completed"):
    lines = (run_dir / "observations.events.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in lines]
    replay = summarize_events(events, exit_kind=exit_kind, adapter="model_server")
    for key in ("coverage", "usage", "requests", "agent_turns"):
        assert replay[key] == measurements[key], key
    return events


@pytest.mark.parametrize(
    ("content", "stream", "error"),
    [
        ("eof-stream", True, "upstream_response_incomplete"),
        ("eof-after-finish", True, "upstream_response_incomplete"),
        ("truncated", False, "upstream_response_truncated"),
        ("malformed", False, "upstream_response_incomplete"),
    ],
)
def test_an_upstream_that_ends_before_its_completion_counts_failed(
    served, tmp_path, content, stream, error
):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        assert ask(collector, content, stream=stream)[0] == 200
        measurements = collector.finalize(exit_kind="completed")
    assert measurements["requests"] == []
    assert measurements["coverage"]["failed_requests"] == 1
    assert measurements["coverage"]["unfinished_requests"] == 0
    assert "relayed_request_incomplete" in measurements["usage"]["reasons"]
    events = assert_replay_agrees(run_dir, measurements)
    assert events[-1]["error"] == error
    transcript = json.loads((run_dir / "model-transcript.jsonl").read_text())
    assert transcript["error"] == error
    if stream:
        assert transcript["response"]["content"] == "partial"


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("content", ["done", "no-usage"])
def test_a_finished_response_counts_whether_or_not_it_reports_usage(
    served, tmp_path, content, stream
):
    plan = plan_model_server(served.spec, served.host, served.state)
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan) as collector:
        ask(collector, content, stream=stream)
        measurements = collector.finalize(exit_kind="completed")
    assert measurements["coverage"]["failed_requests"] == 0
    assert len(measurements["requests"]) == 1
    reasons = measurements["usage"]["reasons"]
    assert ("response_usage_missing" in reasons) == (content == "no-usage")
    assert_replay_agrees(run_dir, measurements)


@pytest.mark.parametrize(
    ("plan", "failed", "unfinished"),
    [
        # The terminal write fails; its fallback is written and counts the request failed.
        ([None, "error"], 1, 0),
        # Half a line is written before the failure; it is cut back before the fallback.
        ([None, "partial"], 1, 0),
        # Nothing more can be written: the durable start leaves the request unfinished.
        ([None, *["error"] * 5], 1, 1),
    ],
)
def test_a_terminal_event_counts_only_once_it_is_written(
    served, tmp_path, monkeypatch, plan, failed, unfinished
):
    run_dir = tmp_path / "run"
    server = plan_model_server(served.spec, served.host, served.state)
    with ModelRelayCollector(run_dir, plan=server) as collector:
        failing_writes(monkeypatch, collector._sink, plan)
        ask(collector, "done")
        measurements = collector.finalize(exit_kind="completed")
    assert measurements["requests"] == []
    assert measurements["coverage"]["failed_requests"] == failed
    assert measurements["coverage"]["unfinished_requests"] == unfinished
    assert_replay_agrees(run_dir, measurements)


def test_a_file_that_cannot_be_cut_back_stops_admitting(served, tmp_path, monkeypatch):
    from silverquillm.karn import model_server

    run_dir = tmp_path / "run"
    server = plan_model_server(served.spec, served.host, served.state)
    with ModelRelayCollector(run_dir, plan=server) as collector:
        failing_writes(monkeypatch, collector._sink, [None, "partial"])
        real = model_server.os.ftruncate

        def ftruncate(fd, length):
            if fd == collector._sink.fd:
                raise OSError(5, "Input/output error")
            return real(fd, length)

        monkeypatch.setattr(model_server.os, "ftruncate", ftruncate)
        ask(collector, "done")
        with pytest.raises(urllib.error.HTTPError) as refused:
            ask(collector, "again")
        assert refused.value.code == 503
        measurements = collector.finalize(exit_kind="completed")
    assert measurements["coverage"]["relayed_requests"] == 1
    assert measurements["coverage"]["unfinished_requests"] == 1
    # Recovery reads the whole lines before the cut and counts the same request unfinished.
    first, cut = (run_dir / "observations.events.jsonl").read_text().splitlines()
    replay = summarize_events([json.loads(first)], exit_kind="completed", adapter="model_server")
    assert replay["coverage"] == measurements["coverage"]
    with pytest.raises(ValueError):
        json.loads(cut)


def test_a_lost_transcript_row_never_changes_the_requests_record(served, tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    server = plan_model_server(served.spec, served.host, served.state)
    with ModelRelayCollector(run_dir, plan=server) as collector:
        failing_writes(monkeypatch, collector._transcript, ["error"])
        ask(collector, "done")
        ask(collector, "again")
        measurements = collector.finalize(exit_kind="completed")
    assert len(measurements["requests"]) == 2
    assert measurements["coverage"]["failed_requests"] == 0
    assert measurements["coverage"]["transcript_rows_missing"] == 1
    events = assert_replay_agrees(run_dir, measurements)
    assert sum(event["kind"] == "response" for event in events) == 2
    assert len((run_dir / "model-transcript.jsonl").read_text().splitlines()) == 1


def test_a_cancelled_request_whose_record_cannot_be_written_stays_unfinished(
    served, tmp_path, monkeypatch
):
    run_dir = tmp_path / "run"
    server = plan_model_server(served.spec, served.host, served.state)
    with ModelRelayCollector(run_dir, plan=server) as collector:
        failing_writes(monkeypatch, collector._sink, [None, *["error"] * 5])
        in_background(collector.endpoint + "/v1/chat/completions", "hold")
        held(served)
        measurements = collector.finalize(exit_kind="deadline")
    assert measurements["coverage"]["unfinished_requests"] == 1
    assert_replay_agrees(run_dir, measurements, "deadline")


def events_file_faults(monkeypatch, plan, *, cut_back=True):
    """Runs ``plan`` (as ``failing_writes`` does, plus "unterminated", which writes all but
    the newline) against the events file of whatever run starts next; with ``cut_back``
    false, cutting a failed append back fails too."""
    from silverquillm.karn import model_server

    files, real_init = [], model_server._EventFile.__init__
    real_write, real_truncate, plan = model_server.os.write, model_server.os.ftruncate, list(plan)

    def init(self, path):
        real_init(self, path)
        if path.name == "observations.events.jsonl":
            files.append(self.fd)

    def write(fd, data):
        if fd not in files or not plan or (step := plan.pop(0)) is None:
            return real_write(fd, data)
        if step in ("partial", "unterminated"):
            plan.insert(0, "error")
            return real_write(fd, bytes(data[: len(data) // 2 if step == "partial" else -1]))
        raise OSError(28, "No space left on device")

    def ftruncate(fd, length):
        if fd in files and not cut_back:
            raise OSError(5, "Input/output error")
        return real_truncate(fd, length)

    monkeypatch.setattr(model_server._EventFile, "__init__", init)
    monkeypatch.setattr(model_server.os, "write", write)
    monkeypatch.setattr(model_server.os, "ftruncate", ftruncate)


@pytest.mark.parametrize(
    ("plan", "requests", "tail_cut"),
    [
        # The terminal event is whole JSON short of its newline, and cannot be cut back.
        ([None, "unterminated"], 0, True),
        # Half the terminal event is left, and cannot be cut back.
        ([None, "partial"], 0, True),
        # Every line is whole.
        ([], 1, False),
    ],
)
def test_recovery_reads_only_the_lines_the_relay_committed(
    served, tmp_path, monkeypatch, plan, requests, tail_cut
):
    opts = model_server_run(served, tmp_path)
    with monkeypatch.context() as patch:
        events_file_faults(patch, plan, cut_back=False)
        run_dir = interrupted_run(opts, "tail")
    live = json.loads((run_dir / "observations.json").read_text())
    recovered = recover(opts, "tail", monkeypatch, tmp_path).run_metadata["measurements"]
    assert len(live["requests"]) == len(recovered["requests"]) == requests
    assert recovered["coverage"] == live["coverage"]
    assert recovered["usage"]["value"] == live["usage"]["value"]
    assert ("interrupted_observation_line" in recovered["usage"]["reasons"]) == tail_cut


def test_a_runner_that_died_before_a_newline_leaves_its_request_unfinished(
    served, tmp_path, monkeypatch
):
    opts = model_server_run(served, tmp_path)
    run_dir = interrupted_run(opts, "died")
    events = run_dir / "observations.events.jsonl"
    # The runner died between the event's last two writes: the line parses but never ended.
    events.write_bytes(events.read_bytes().removesuffix(b"\n"))
    assert json.loads(events.read_text().splitlines()[-1])["kind"] == "response"
    measurements = recover(opts, "died", monkeypatch, tmp_path).run_metadata["measurements"]
    assert measurements["requests"] == []
    assert measurements["coverage"]["unfinished_requests"] == 1
    assert "interrupted_observation_line" in measurements["usage"]["reasons"]


@pytest.mark.parametrize("alias", ["gpt-6-sol", "qwen3.8-27b"])
def test_a_local_model_is_never_priced_as_a_hosted_one(served, tmp_path, alias):
    spec = model_server_spec(
        runtime(
            spec_document(model={"file": "model.gguf", "sha256": served.spec.model_sha256}),
            CONSTRUCT_MODEL=alias,
        )
    )
    run_dir = tmp_path / "run"
    with ModelRelayCollector(run_dir, plan=plan_model_server(spec, served.host, served.state)) as c:
        ask(c, "done")
        measurements = c.finalize(exit_kind="completed")
    assert measurements["requests"][0]["model"] == alias
    _, replay = replayed(run_dir, "completed")
    for summary in (measurements, replay):
        assert [row["usd"] for row in summary["request_prices"]] == [None]
        assert summary["request_prices"][0]["reasons"] == ["model_price_unavailable"]
        assert summary["estimated_cost"]["value"] is None
        assert "model_price_unavailable" in summary["estimated_cost"]["reasons"]
        assert summary["cost_breakdown"]["value"] is None
        assert summary["price_table"]["models"] == {}


# The recipe owns the server's flags, files, environment and timeouts (#271).

RECIPE_Q8 = (
    '{"engine":"llama.cpp","build":"b12182","model":{"file":"Qwen3.8-27B-UD-Q8_K_XL.gguf",'
    '"sha256":"' + "a" * 64 + '"},"arguments":["-c","262144","-np","1","-ngl","999","-fa","on",'
    '"-ctk","f16","-ctv","f16","--fit","off","--jinja","--temp","1.0","--top-p","0.95",'
    '"--top-k","20","--min-p","0"]}'
)


def test_a_recipe_written_before_files_records_exactly_what_it_did():
    spec = model_server_spec(
        {
            "environment": {
                "CONSTRUCT_MODEL": "qwen3.8-27b",
                "CONSTRUCT_PI_BASE_URL": MODEL_SERVER_URL,
                MODEL_SERVER_ENV: RECIPE_Q8,
            },
            "network": {"mode": "restricted", "https_hosts": []},
        }
    )
    assert spec.to_dict() == {
        "engine": "llama.cpp",
        "build": "b12182",
        "model": {"file": "Qwen3.8-27B-UD-Q8_K_XL.gguf", "sha256": "a" * 64},
        "arguments": json.loads(RECIPE_Q8)["arguments"],
        "served_model": "qwen3.8-27b",
    }
    assert spec.ready_timeout == 900 and spec.request_timeout == 1800


def test_an_unlisted_flag_passes_and_is_kept_with_the_arguments():
    arguments = ["--spec-type", "ngram-simple", "--spec-default", "--cors-origins", "x"]
    spec = model_server_spec(runtime(spec_document(arguments=arguments)))
    assert spec.arguments == tuple(arguments)


def test_a_debug_variable_that_writes_nothing_passes():
    document = spec_document(environment={"CUBLASLT_LOG_LEVEL": "1", "GGML_SCHED_DEBUG": "1"})
    assert model_server_spec(runtime(document)) is not None


def with_files(*files, **overrides):
    document = spec_document(**overrides)
    del document["model"]
    document["files"] = list(files)
    return document


@pytest.mark.parametrize(
    ("files", "reason"),
    [
        ([{"file": "a.gguf", "sha256": "0" * 64}], "model_server_files_need_one_model"),
        (
            [
                {"file": "a.gguf", "sha256": "0" * 64, "flag": "--model"},
                {"file": "b.gguf", "sha256": "0" * 64, "flag": "--model"},
            ],
            "model_server_files_need_one_model",
        ),
        ([{"file": "../a.gguf", "sha256": "0" * 64, "flag": "--model"}], "files_invalid"),
        ([{"file": "/etc/passwd", "sha256": "0" * 64, "flag": "--model"}], "files_invalid"),
        ([{"file": "a.gguf", "sha256": "0" * 64, "flag": "-m"}], "file_flag_not_allowed:-m"),
        (
            [
                {"file": "a.gguf", "sha256": "0" * 64, "flag": "--model"},
                {"file": "k.pem", "sha256": "0" * 64, "flag": "--ssl-key-file"},
            ],
            "file_flag_not_allowed:--ssl-key-file",
        ),
        (
            [{"file": "Q-00001-of-00002.gguf", "sha256": "0" * 64, "flag": "--model"}],
            "model_server_split_model_incomplete:Q",
        ),
    ],
)
def test_declared_files_are_refused_when_they_cannot_all_be_verified(files, reason):
    with pytest.raises(KarnError, match=reason):
        model_server_spec(runtime(with_files(*files)))


def test_both_model_and_files_is_refused():
    document = with_files({"file": "a.gguf", "sha256": "0" * 64, "flag": "--model"})
    document["model"] = {"file": "a.gguf", "sha256": "0" * 64}
    with pytest.raises(KarnError, match="model_server_spec_invalid"):
        model_server_spec(runtime(document))


@pytest.fixture
def drafted(served):
    """A recipe with a split model, a draft model and a chat template, all verified."""
    models = served.host.models_dir
    contents = {
        "Q-00001-of-00002.gguf": b"part one",
        "Q-00002-of-00002.gguf": b"part two",
        "draft.gguf": b"draft weights",
        "chat.jinja": b"{{ messages }}",
    }
    for name, content in contents.items():
        (models / name).write_bytes(content)
    files = [
        {"file": "Q-00001-of-00002.gguf", "sha256": "", "flag": "--model"},
        {"file": "Q-00002-of-00002.gguf", "sha256": ""},
        {"file": "draft.gguf", "sha256": "", "flag": "-md"},
        {"file": "chat.jinja", "sha256": "", "flag": "--chat-template-file"},
    ]
    for entry in files:
        entry["sha256"] = file_sha256(models / entry["file"])
    document = with_files(
        *files,
        arguments=["--spec-type", "draft-simple", "--jinja"],
        environment={"GGML_CUDA_GRAPH_OPT": "1"},
        ready_timeout_seconds=60,
        request_timeout_seconds=7200,
    )
    return SimpleNamespace(served=served, files=files, spec=model_server_spec(runtime(document)))


def test_declared_files_are_verified_passed_and_recorded(drafted, tmp_path):
    served = drafted.served
    host = ModelServerHost(served.host.models_dir, served.host.llama_cpp, {"LD_LIBRARY_PATH": "/x"})
    plan = plan_model_server(drafted.spec, host, served.state)
    with ModelRelayCollector(tmp_path / "run", plan=plan) as collector:
        argv = json.loads(Path(str(served.binary) + ".argv").read_text())
        models = served.host.models_dir.resolve()
        assert argv[argv.index("--model") + 1] == str(models / "Q-00001-of-00002.gguf")
        assert argv[argv.index("-md") + 1] == str(models / "draft.gguf")
        assert argv[argv.index("--chat-template-file") + 1] == str(models / "chat.jinja")
        assert "Q-00002-of-00002.gguf" not in " ".join(argv)
        facts = collector.facts
        assert facts["model_sha256_verified"] is True
        assert set(facts["file_bytes"]) == {entry["file"] for entry in drafted.files}
        assert facts["files"] == drafted.files
        assert facts["environment"] == {"GGML_CUDA_GRAPH_OPT": "1"}
        assert facts["ready_timeout_seconds"] == 60 and collector.llama.ready_seconds == 60
        assert facts["ready_seconds"] < 60
        assert facts["request_timeout_seconds"] == 7200
        assert facts["host"] == {
            "environment": {"LD_LIBRARY_PATH": "/x"},
            "binary_sha256": hashlib.sha256(served.binary.read_bytes()).hexdigest(),
        }


def test_any_declared_file_that_changed_is_refused_before_the_server_starts(drafted, tmp_path):
    served = drafted.served
    plan = plan_model_server(drafted.spec, served.host, served.state)
    (served.host.models_dir / "Q-00002-of-00002.gguf").write_bytes(b"other part")
    with pytest.raises(KarnError, match="model_file_digest_mismatch:Q-00002-of-00002.gguf"):
        ModelRelayCollector(tmp_path / "run", plan=plan).__enter__()
    assert not Path(str(served.binary) + ".argv").exists()


def test_a_missing_declared_file_is_refused_before_any_evidence(drafted):
    (drafted.served.host.models_dir / "draft.gguf").unlink()
    with pytest.raises(KarnError, match="model_file_unavailable:draft.gguf"):
        plan_model_server(drafted.spec, drafted.served.host, drafted.served.state)


def test_the_server_never_inherits_the_runners_environment(served, tmp_path, monkeypatch):
    monkeypatch.setenv("LLAMA_ARG_CTX_SIZE", "4096")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/old-llama")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    monkeypatch.delenv("CUDA_DEVICE_ORDER", raising=False)
    document = spec_document(
        model=served.spec.to_dict()["model"], environment={"GGML_CUDA_GRAPH_OPT": "1"}
    )
    spec = model_server_spec(runtime(document))
    host = ModelServerHost(served.host.models_dir, served.host.llama_cpp, {"HOST_ONLY": "yes"})
    with ModelRelayCollector(tmp_path / "run", plan=plan_model_server(spec, host, served.state)):
        environment = json.loads(Path(str(served.binary) + ".env").read_text())
    assert "LLAMA_ARG_CTX_SIZE" not in environment
    assert "LD_LIBRARY_PATH" not in environment
    # Without GPU Slots only the runner's own GPU selection passes, exactly as set.
    assert environment["CUDA_VISIBLE_DEVICES"] == "3"
    assert "CUDA_DEVICE_ORDER" not in environment
    assert environment["PATH"] == os.environ["PATH"]
    assert environment["HOST_ONLY"] == "yes"
    assert environment["GGML_CUDA_GRAPH_OPT"] == "1"
    # An empty bench-owned home: llama.cpp finds no user-level config.ini.
    home = tmp_path / "run" / "model-server-home"
    assert environment["HOME"] == str(home)
    assert environment["XDG_CONFIG_HOME"] == str(home / ".config")
    assert list(home.iterdir()) == []


def test_the_version_probe_runs_in_the_servers_environment(served, monkeypatch):
    monkeypatch.setenv("CUDA_DEVICE_ORDER", "FASTEST_FIRST")
    monkeypatch.setenv("LLAMA_ARG_CTX_SIZE", "4096")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/old-llama")
    host = ModelServerHost(
        served.host.models_dir, served.host.llama_cpp, {"LD_LIBRARY_PATH": "/opt/cuda/lib64"}
    )
    plan_model_server(served.spec, host, served.state)
    environment = json.loads(Path(str(served.binary) + ".version-env").read_text())
    assert environment["LD_LIBRARY_PATH"] == "/opt/cuda/lib64"
    assert "LLAMA_ARG_CTX_SIZE" not in environment
    assert environment["HOME"] != os.environ.get("HOME")
    assert environment["XDG_CONFIG_HOME"].startswith(environment["HOME"])
    assert environment["CUDA_DEVICE_ORDER"] == "FASTEST_FIRST"


def test_a_system_config_file_llama_cpp_would_read_refuses_the_run(served, tmp_path, monkeypatch):
    from silverquillm.karn import model_server

    config = tmp_path / "etc" / "llama.cpp" / "config.ini"
    config.parent.mkdir(parents=True)
    config.write_text("[*]\nctx-size = 4096\n")
    monkeypatch.setattr(model_server, "SYSTEM_CONFIG_FILES", (config,))
    with pytest.raises(KarnError, match="model_server_config_file_present:" + str(config)):
        plan_model_server(served.spec, served.host, served.state)


def test_setpriv_is_found_on_the_runners_path_or_the_run_is_refused(served, monkeypatch):
    from silverquillm.karn import model_server

    plan = plan_model_server(served.spec, served.host, served.state)
    command = model_server.LlamaServer(plan, Path("/unused")).command(1234)
    assert Path(command[0]).is_absolute() and Path(command[0]).name == "setpriv"
    monkeypatch.setattr(model_server.shutil, "which", lambda name: None)
    with pytest.raises(KarnError, match="model_server_setpriv_unavailable"):
        plan_model_server(served.spec, served.host, served.state)


def test_a_linked_file_is_passed_by_its_declared_name_inside_the_models_directory(served, tmp_path):
    models = served.host.models_dir
    (models / "store").mkdir()
    for number in (1, 2):
        (models / "store" / f"blob{number}").write_bytes(b"part %d" % number)
        (models / f"Q-0000{number}-of-00002.gguf").symlink_to(models / "store" / f"blob{number}")
    files = [
        {"file": "Q-00001-of-00002.gguf", "sha256": "", "flag": "--model"},
        {"file": "Q-00002-of-00002.gguf", "sha256": ""},
    ]
    for entry in files:
        entry["sha256"] = file_sha256(models / entry["file"])
    spec = model_server_spec(runtime(with_files(*files)))
    plan = plan_model_server(spec, served.host, served.state)
    with ModelRelayCollector(tmp_path / "run", plan=plan):
        argv = json.loads(Path(str(served.binary) + ".argv").read_text())
    assert argv[argv.index("--model") + 1] == str(models.resolve() / "Q-00001-of-00002.gguf")
    outside = tmp_path / "outside.gguf"
    outside.write_bytes(b"elsewhere")
    (models / "escape.gguf").symlink_to(outside)
    escape = [{"file": "escape.gguf", "sha256": file_sha256(outside), "flag": "--model"}]
    with pytest.raises(KarnError, match="model_file_unavailable:escape.gguf"):
        plan_model_server(
            model_server_spec(runtime(with_files(*escape))), served.host, served.state
        )


@pytest.mark.parametrize(
    ("token", "normalized"),
    [
        ("--hf_repo", "--hf-repo"),
        ("--model_url", "--model-url"),
        ("--api_key", "--api-key"),
        ("--log_file", "--log-file"),
        ("--slot_save_path", "--slot-save-path"),
        ("--media_path", "--media-path"),
        ("--model_draft", "--model-draft"),
        ("--chat_template_file", "--chat-template-file"),
        ("--lora_scaled", "--lora-scaled"),
        ("--mcp_servers_json", "--mcp-servers-json"),
        ("--webui_mcp_proxy", "--webui-mcp-proxy"),
        ("--connect_code", "--connect-code"),
        ("--reuse_port", "--reuse-port"),
        ("--binary_file", "--binary-file"),
        ("--gpt_oss_20b_default", "--gpt-oss-20b-default"),
        ("--host_name_is=not-a-flag", None),
    ],
)
def test_a_flag_spelled_with_underscores_is_the_flag_llama_cpp_reads(token, normalized):
    document = spec_document(arguments=[token, "value"])
    if normalized is None:
        assert model_server_spec(runtime(document)) is not None
        return
    with pytest.raises(KarnError, match="model_server_flag_not_allowed:" + normalized):
        model_server_spec(runtime(document))


def test_a_value_spelled_as_a_refused_flag_is_refused():
    with pytest.raises(KarnError, match="model_server_flag_not_allowed:--hf-repo"):
        model_server_spec(runtime(spec_document(arguments=["--temp", "--hf_repo"])))


def test_the_recipe_environment_overrides_the_hosts():
    from silverquillm.karn.model_server import server_environment

    spec = model_server_spec(runtime(spec_document(environment={"SHARED": "recipe"})))
    inherited = {"PATH": "/bin", "HOME": "/h", "OTHER": "x"}
    assert server_environment(spec, {"SHARED": "host"}, Path("/run/home"), inherited) == {
        "PATH": "/bin",
        "HOME": "/run/home",
        "XDG_CONFIG_HOME": "/run/home/.config",
        "SHARED": "recipe",
    }


@pytest.mark.parametrize(
    ("environment", "reason"),
    [
        ({"LLAMA_ARG_CTX_SIZE": "4096"}, "model_server_environment_refused:LLAMA_ARG_CTX_SIZE"),
        *(
            ({name: "x"}, "model_server_environment_refused:" + name)
            for name in (
                *("LLAMA_API_KEY", "LLAMA_CACHE", "LLAMA_SERVER_ROUTER_PORT"),
                *("LLAMACPP_TEST_MODELFILE", "AIP_HTTP_PORT", "AIP_PREDICT_ROUTE"),
                *("GGML_BACKEND_PATH", "GGML_ET_KERNELS_PATH", "GGML_OPENCL_KERNEL_CACHE_DIR"),
                *("LD_PRELOAD", "LD_LIBRARY_PATH", "PATH", "HOME", "XDG_CONFIG_HOME"),
                *("HF_TOKEN", "HF_ENDPOINT", "HUGGING_FACE_HUB_TOKEN", "MODEL_ENDPOINT"),
                *("MTMD_BACKEND_DEVICE", "http_proxy", "HTTPS_PROXY", "All_Proxy", "no_proxy"),
                "__LLAMA_X",
                *("CUDA_INJECTION64_PATH", "CUDA_AMODEL_DLL", "CUDA_FORCE_PRELOAD_LIBRARIES"),
                *("CUDA_DEVCODE_PATH", "CUDA_MPS_PIPE_DIRECTORY", "CUDA_CACHE_PATH"),
                *("CUDA_LOG_FILE", "CUDA_COREDUMP_FILE", "CUBLASLT_LOG_FILE", "CUBLAS_LOGDEST_DBG"),
                *("CUDA_ENABLE_COREDUMP_ON_EXCEPTION", "MTMD_DEBUG_EMBEDDINGS"),
                *("HUGGINGFACE_HUB_CACHE", "OPENSSL_CONF", "OPENSSL_MODULES", "SSL_CERT_FILE"),
                *("SSL_CERT_DIR", "GGML_ET_PROFILE", "ET_TOOLCHAIN", "GCONV_PATH"),
            )
        ),
        ({"CUDA_VISIBLE_DEVICES": "0"}, "model_server_environment_refused:CUDA_VISIBLE"),
        ({"CUDA_DEVICE_ORDER": "FASTEST_FIRST"}, "model_server_environment_refused:CUDA_DEVICE"),
        ({"BAD NAME": "x"}, "model_server_environment_invalid"),
        ({"X": 1}, "model_server_environment_invalid"),
        ({"X": "a\0b"}, "model_server_environment_invalid"),
        (["X=1"], "model_server_environment_invalid"),
    ],
)
def test_a_recipe_environment_that_would_change_the_record_is_refused(environment, reason):
    with pytest.raises(KarnError, match=reason):
        model_server_spec(runtime(spec_document(environment=environment)))


@pytest.mark.parametrize(
    ("key", "value"),
    [("ready_timeout_seconds", 0), ("ready_timeout_seconds", "60")]
    + [("request_timeout_seconds", True)]
    + [("request_timeout_seconds", 86401)],
)
def test_a_timeout_must_be_a_bounded_number_of_seconds(key, value):
    with pytest.raises(KarnError, match="model_server_timeout_invalid:" + key):
        model_server_spec(runtime(spec_document(**{key: value})))


def test_the_host_config_names_an_environment_only_this_host_needs(tmp_path):
    from silverquillm.host_config import HostConfigError, load_host_config

    path = tmp_path / "config.toml"
    path.write_text('[model_server.environment]\nLD_LIBRARY_PATH = "/opt/cuda/lib64"\n')
    assert load_host_config(path).model_server_environment == {"LD_LIBRARY_PATH": "/opt/cuda/lib64"}
    path.write_text('[model_server.environment]\nLLAMA_ARG_N_GPU_LAYERS = "0"\n')
    with pytest.raises(HostConfigError, match="refused:LLAMA_ARG_N_GPU_LAYERS"):
        load_host_config(path)
    for name in ("LD_PRELOAD", "PATH", "LLAMA_CACHE", "https_proxy", "CUDA_INJECTION64_PATH"):
        path.write_text(f'[model_server.environment]\n{name} = "x"\n')
        with pytest.raises(HostConfigError, match="refused:" + name):
            load_host_config(path)
    with pytest.raises(KarnError, match="model_server_host_environment_refused:CUDA"):
        plan_model_server(
            model_server_spec(runtime()),
            ModelServerHost(tmp_path, {}, {"CUDA_VISIBLE_DEVICES": "0"}),
            tmp_path,
        )


# The recipe's request timeout governs every hop of a model request (#275 review).


def test_the_recipe_request_timeout_reaches_the_sidecar_launch(served, tmp_path):
    from silverquillm.karn.execution import run_benchmark

    seen = {}

    class TimedHost(RelayHost):
        def run(self, *args, model_timeout_seconds, **kwargs):
            seen["timeout"] = model_timeout_seconds
            return super().run(*args, **kwargs)

    for document, expected in (
        (spec_document(model=served.spec.to_dict()["model"], request_timeout_seconds=7200), 7200),
        (spec_document(model=served.spec.to_dict()["model"]), 1800),
    ):
        opts = model_server_run(served, tmp_path / str(expected))
        candidate_dir = tmp_path / str(expected) / "recipe"
        definition = next(candidate_dir.rglob("definition.json"))
        data = json.loads(definition.read_text())
        data["runtime"]["environment"][MODEL_SERVER_ENV] = json.dumps(document)
        definition.write_text(json.dumps(data))
        opts["host"] = TimedHost()
        try:
            run_benchmark(**opts, run_id="timed")
        except KarnError:
            pass
        assert seen.pop("timeout", None) == expected
    docker = NetworkDocker()
    policy = {"mode": "restricted", "https_hosts": []}
    with Network(
        docker,
        "r1",
        policy,
        "sha256:" + "1" * 64,
        tmp_path,
        model_endpoint="http://h:1/model/x",
        model_timeout_seconds=7200,
    ):
        create = next(command for command in docker.commands if command[0] == "create")
        assert "SILVERQUILLM_MODEL_TIMEOUT=7200" in create


def test_the_sidecar_waits_on_the_relay_as_long_as_it_was_configured(monkeypatch):
    from silverquillm.karn import proxy

    forward = proxy.model_forward_from_environment(
        {
            "SILVERQUILLM_MODEL_ENDPOINT": "http://127.0.0.1:9/model/x",
            "SILVERQUILLM_MODEL_CLIENTS": "127.0.0.0/8",
            "SILVERQUILLM_MODEL_TIMEOUT": "7200",
        },
        ("127.0.0.1", 0),
    )
    timeouts, real_connect = [], socket.create_connection

    def connect(address, timeout):
        if address != ("127.0.0.1", 9):
            return real_connect(address, timeout=timeout)
        timeouts.append(timeout)
        raise OSError("relay unreachable in this test")

    monkeypatch.setattr(proxy.socket, "create_connection", connect)
    thread = threading.Thread(target=forward.serve_forever, daemon=True)
    thread.start()
    try:
        with real_connect(forward.server_address, timeout=5) as client:
            client.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
            assert b"403" in client.recv(4096)
    finally:
        forward.shutdown()
        forward.server_close()
        thread.join()
    assert timeouts == [7200]
    assert proxy.model_forward_from_environment({}) is None
    default = proxy.model_forward_from_environment(
        {"SILVERQUILLM_MODEL_ENDPOINT": "http://h:1/x", "SILVERQUILLM_MODEL_CLIENTS": "10.0.0.0/8"},
        ("127.0.0.1", 0),
    )
    assert default.model_timeout == 1800
    default.server_close()


def delayed_request(served, tmp_path, *, recipe_timeout, sidecar_timeout, delay):
    """One non-streaming request that the fake server answers after *delay* seconds, sent
    through a real sidecar route and relay; returns the client's outcome and measurements."""
    document = spec_document(
        model=served.spec.to_dict()["model"], request_timeout_seconds=recipe_timeout
    )
    plan = plan_model_server(model_server_spec(runtime(document)), served.host, served.state)
    with ModelRelayCollector(tmp_path / "run", plan=plan) as collector:
        forward = ModelForwardServer(
            ("127.0.0.1", 0), collector.endpoint, model_timeout=sidecar_timeout
        )
        thread = threading.Thread(target=forward.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{forward.server_address[1]}/v1/chat/completions"
            try:
                status, body = post(
                    url, {"stream": False, "messages": [{"role": "user", "content": delay}]}
                )
                outcome = (status, json.loads(body)["choices"][0]["finish_reason"])
            except (urllib.error.HTTPError, urllib.error.URLError, ConnectionError) as error:
                outcome = (getattr(error, "code", None), type(error).__name__)
            time.sleep(0.2)
        finally:
            forward.shutdown()
            forward.server_close()
            thread.join()
        measurements = collector.finalize(exit_kind="completed")
    return outcome, measurements


def test_a_request_slower_than_the_old_limit_succeeds_within_the_recipes(
    served, tmp_path, monkeypatch
):
    from silverquillm.karn import proxy

    # The old fixed limit, scaled down to 1 s: the recipe's 15 s limit must win on every hop,
    # with a wide margin either side of the 2 s answer for a loaded machine.
    monkeypatch.setattr(proxy, "DEFAULT_MODEL_TIMEOUT_SECONDS", 1)
    outcome, measurements = delayed_request(
        served, tmp_path, recipe_timeout=15, sidecar_timeout=15, delay="delay:2"
    )
    assert outcome == (200, "stop")
    assert measurements["coverage"]["relayed_requests"] == 1
    assert measurements["coverage"]["failed_requests"] == 0
    assert measurements["requests"][0]["finish_reason"] == "stop"


# Each hop's limit is tested alone, the other's set far above the delay, so exactly one hop
# can give up and the outcome does not depend on which gives up first.


def test_a_request_past_the_relays_limit_fails_and_is_counted_failed(served, tmp_path):
    outcome, measurements = delayed_request(
        served, tmp_path, recipe_timeout=1, sidecar_timeout=60, delay="delay:6"
    )
    # The relay gave up on the server and answered; the sidecar passed the answer on.
    assert outcome == (502, "HTTPError")
    coverage = measurements["coverage"]
    assert coverage["relayed_requests"] == 1
    assert coverage["failed_requests"] == 1
    assert coverage["unfinished_requests"] == 0
    assert measurements["requests"] == []
    assert "relayed_request_incomplete" in measurements["usage"]["reasons"]


def test_a_request_past_the_sidecars_limit_fails_there(served, tmp_path):
    started = time.monotonic()
    outcome, measurements = delayed_request(
        served, tmp_path, recipe_timeout=60, sidecar_timeout=1, delay="delay:6"
    )
    # The sidecar gave up while the relay still waited; the run's end cancels the request.
    assert outcome == (403, "HTTPError")
    assert time.monotonic() - started < 6
    coverage = measurements["coverage"]
    assert coverage["relayed_requests"] == 1
    assert coverage["failed_requests"] == 1
    assert coverage["unfinished_requests"] == 0
    assert "relayed_request_incomplete" in measurements["usage"]["reasons"]


@pytest.mark.parametrize("flag", ["--lora-scaled", "--control-vector-scaled"])
@pytest.mark.parametrize("spelling", ["dash", "underscore"])
def test_scaled_adapters_are_refused_since_files_cannot_carry_a_scale(flag, spelling):
    written = flag.replace("-", "_").replace("__", "--", 1) if spelling == "underscore" else flag
    with pytest.raises(KarnError, match="model_server_flag_not_allowed:" + flag):
        model_server_spec(runtime(spec_document(arguments=[written, "a.gguf:0.5"])))
    files = [
        {"file": "m.gguf", "sha256": "0" * 64, "flag": "--model"},
        {"file": "a.gguf", "sha256": "0" * 64, "flag": written},
    ]
    with pytest.raises(KarnError, match="model_server_file_flag_not_allowed"):
        model_server_spec(runtime(with_files(*files)))


def test_unscaled_adapters_are_verified_and_passed(served, tmp_path):
    models = served.host.models_dir
    (models / "adapter.gguf").write_bytes(b"lora")
    (models / "vector.gguf").write_bytes(b"control")
    files = [
        {"file": "model.gguf", "sha256": served.spec.model_sha256, "flag": "--model"},
        {"file": "adapter.gguf", "sha256": file_sha256(models / "adapter.gguf"), "flag": "--lora"},
        {
            "file": "vector.gguf",
            "sha256": file_sha256(models / "vector.gguf"),
            "flag": "--control-vector",
        },
    ]
    plan = plan_model_server(
        model_server_spec(runtime(with_files(*files))), served.host, served.state
    )
    with ModelRelayCollector(tmp_path / "run", plan=plan):
        argv = json.loads(Path(str(served.binary) + ".argv").read_text())
    assert argv[argv.index("--lora") + 1] == str(models.resolve() / "adapter.gguf")
    assert argv[argv.index("--control-vector") + 1] == str(models.resolve() / "vector.gguf")
