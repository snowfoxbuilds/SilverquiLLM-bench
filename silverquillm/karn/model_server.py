"""A local model server for pi constructs (issue #262).

A recipe that declares ``SILVERQUILLM_MODEL_SERVER`` in its runtime environment is served by
a llama.cpp ``llama-server`` the bench starts on the host, bound to loopback. The workload
reaches it only as ``http://model-server:8080/v1``: the per-run proxy sidecar forwards that
address to a host-side relay, and the relay forwards to the server and records every request.
The recipe's server settings are part of its definition, so each configuration is its own
candidate; the host config only says where this host keeps the builds and the model files.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import http.client
import json
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .definition import KarnError
from .observations import TOKEN_KEYS, _measurements

MODEL_SERVER_ENV = "SILVERQUILLM_MODEL_SERVER"
MODEL_SERVER_HOST = "model-server"
MODEL_SERVER_PORT = 8080
MODEL_SERVER_URL = f"http://{MODEL_SERVER_HOST}:{MODEL_SERVER_PORT}/v1"
TELEMETRY_ADAPTER = "model_server"
THREAD_ID = "main"
EVENTS_FILE = "observations.events.jsonl"
TRANSCRIPT_FILE = "model-transcript.jsonl"
SERVER_LOG = "model-server.log"

# Server flags a recipe may set, and whether each takes a value. The bench owns the model
# file, the address, the alias and the API surface, so every other flag is refused.
SERVER_FLAGS: dict[str, bool] = {
    **dict.fromkeys(("-c", "--ctx-size"), True),
    **dict.fromkeys(("-ctk", "--cache-type-k", "-ctv", "--cache-type-v"), True),
    **dict.fromkeys(("-ngl", "--n-gpu-layers", "--gpu-layers"), True),
    **dict.fromkeys(("-fa", "--flash-attn", "--fit"), True),
    **dict.fromkeys(("-b", "--batch-size", "-ub", "--ubatch-size"), True),
    **dict.fromkeys(("-np", "--parallel", "-t", "--threads", "-tb", "--threads-batch"), True),
    **dict.fromkeys(("-ts", "--tensor-split", "-sm", "--split-mode", "-mg", "--main-gpu"), True),
    **dict.fromkeys(("--temp", "--top-p", "--top-k", "--min-p", "--seed"), True),
    **dict.fromkeys(("--repeat-penalty", "--presence-penalty", "--frequency-penalty"), True),
    **dict.fromkeys(("--chat-template-kwargs", "--reasoning-budget", "--reasoning-format"), True),
    **dict.fromkeys(("--cache-reuse", "-n", "--n-predict"), True),
    **dict.fromkeys(("--rope-scaling", "--rope-scale", "--yarn-orig-ctx"), True),
    **dict.fromkeys(("--jinja", "--swa-full", "--no-warmup"), False),
    **dict.fromkeys(("-kvu", "--kv-unified", "--no-context-shift", "--context-shift"), False),
}
_BUILD = re.compile(r"b([0-9]{1,8})")
_VERSION = re.compile(r"build ([0-9]{1,8}), commit ([0-9a-f]{7,40})")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# A request at the largest context is a few MiB; the cap also bounds the parse here and the
# sidecar's copy, which runs in 128 MiB.
MAX_REQUEST_BYTES = 16 * 1024 * 1024
# What the relay keeps of workload-controlled request content, per field and per request.
MAX_KEPT_FIELD_CHARS = 4096
MAX_KEPT_MESSAGES_CHARS = 1024 * 1024
# Request keys pi sends; any other is a per-request override of the recipe's server settings.
ORDINARY_REQUEST_KEYS = frozenset(
    {"model", "messages", "tools", "stream", "stream_options", "store", "max_completion_tokens"}
)
UPSTREAM_TIMEOUT_SECONDS = 1800
RELAYED_PATHS = {("POST", "/v1/chat/completions"), ("GET", "/v1/models")}


@dataclass(frozen=True)
class ModelServerSpec:
    """The recipe's server: an engine build, one model file, and the server flags."""

    engine: str
    build: str
    model_file: str
    model_sha256: str
    arguments: tuple[str, ...]
    served_model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "build": self.build,
            "model": {"file": self.model_file, "sha256": self.model_sha256},
            "arguments": list(self.arguments),
            "served_model": self.served_model,
        }


def model_server_spec(runtime: dict) -> ModelServerSpec | None:
    """The definition's model server, or None; a malformed one refuses the candidate."""
    environment = runtime["environment"]
    if MODEL_SERVER_ENV not in environment:
        return None
    try:
        document = json.loads(environment[MODEL_SERVER_ENV])
    except ValueError:
        raise KarnError("model_server_spec_invalid") from None
    if not isinstance(document, dict) or set(document) != {
        "engine",
        "build",
        "model",
        "arguments",
    }:
        raise KarnError("model_server_spec_invalid")
    model, arguments = document["model"], document["arguments"]
    if document["engine"] != "llama.cpp":
        raise KarnError("model_server_engine_unsupported")
    if not isinstance(document["build"], str) or not _BUILD.fullmatch(document["build"]):
        raise KarnError("model_server_build_invalid")
    if (
        not isinstance(model, dict)
        or set(model) != {"file", "sha256"}
        or not isinstance(model["file"], str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,200}\.gguf", model["file"])
        # Only the named file is verified, so a split model's other parts would load unchecked.
        or re.search(r"-[0-9]{5}-of-[0-9]{5}\.gguf$", model["file"])
        or not isinstance(model["sha256"], str)
        or not _SHA256.fullmatch(model["sha256"])
    ):
        raise KarnError("model_server_model_invalid")
    if not isinstance(arguments, list) or not all(isinstance(a, str) for a in arguments):
        raise KarnError("model_server_arguments_invalid")
    position = 0
    while position < len(arguments):
        flag = arguments[position]
        if flag not in SERVER_FLAGS:
            raise KarnError("model_server_flag_not_allowed:" + flag[:64])
        position += 2 if SERVER_FLAGS[flag] else 1
        if position > len(arguments):
            raise KarnError("model_server_flag_value_missing:" + flag)
    if any("\0" in argument for argument in arguments):
        raise KarnError("model_server_arguments_invalid")
    served = environment.get("CONSTRUCT_MODEL", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", served):
        raise KarnError("model_server_requires_construct_model")
    if environment.get("CONSTRUCT_PI_BASE_URL") != MODEL_SERVER_URL:
        raise KarnError("model_server_url_mismatch")
    if runtime["network"]["mode"] != "restricted":
        raise KarnError("model_server_requires_restricted_network")
    return ModelServerSpec(
        "llama.cpp",
        document["build"],
        model["file"],
        model["sha256"],
        tuple(arguments),
        served,
    )


@dataclass(frozen=True)
class ModelServerHost:
    """Where this host keeps llama.cpp builds and model files (host config ``[model_server]``)."""

    models_dir: Path | None = None
    llama_cpp: dict[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelServerPlan:
    """A spec resolved against this host before any evidence exists."""

    spec: ModelServerSpec
    binary: Path
    version: str
    commit: str
    model_path: Path
    lock_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.spec.to_dict(),
            "binary": str(self.binary),
            "binary_version": self.version,
            "binary_commit": self.commit,
            "model_path": str(self.model_path),
        }


def plan_model_server(spec: ModelServerSpec, host: ModelServerHost, state_root: Path):
    """Refuse a server this host cannot start: a missing build or file, or the wrong build."""
    binary = host.llama_cpp.get(spec.build)
    if binary is None:
        raise KarnError("model_server_build_unavailable:" + spec.build)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise KarnError("model_server_binary_unavailable:" + spec.build)
    try:
        result = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        raise KarnError("model_server_binary_unavailable:" + spec.build) from None
    found = _VERSION.search(result.stdout + result.stderr)
    if found is None or found.group(1) != _BUILD.fullmatch(spec.build).group(1):
        raise KarnError("model_server_build_mismatch:" + spec.build)
    if host.models_dir is None:
        raise KarnError("model_server_models_dir_unset")
    model_path = (host.models_dir / spec.model_file).resolve()
    if not model_path.is_file():
        raise KarnError("model_file_unavailable:" + spec.model_file)
    return ModelServerPlan(
        spec,
        binary.resolve(),
        found.group(0),
        found.group(2),
        model_path,
        Path(state_root).resolve() / "model-server.lock",
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class LlamaServer:
    """One loopback ``llama-server`` for one run, stopped with it."""

    def __init__(self, plan: ModelServerPlan, log_path: Path, *, ready_seconds: float = 900):
        self.plan, self.log_path, self.ready_seconds = plan, log_path, ready_seconds
        self.process: subprocess.Popen | None = None
        self.port: int | None = None

    def command(self, port: int) -> list[str]:
        spec = self.plan.spec
        return [
            # The parent-death signal: a runner killed outright must not leave the GPUs held.
            "setpriv",
            "--pdeathsig",
            "TERM",
            "--",
            str(self.plan.binary),
            "--model",
            str(self.plan.model_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--alias",
            spec.served_model,
            "--no-webui",
            *spec.arguments,
        ]

    def __enter__(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        log = self.log_path.open("ab")
        try:
            self.process = subprocess.Popen(
                self.command(self.port),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        finally:
            log.close()
        try:
            self._wait_ready()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _wait_ready(self):
        deadline = time.monotonic() + self.ready_seconds
        while True:
            if self.process.poll() is not None:
                raise KarnError("model_server_exited_before_ready")
            with contextlib.suppress(OSError, http.client.HTTPException):
                connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
                try:
                    connection.request("GET", "/health")
                    if connection.getresponse().status == 200:
                        return
                finally:
                    connection.close()
            if time.monotonic() >= deadline:
                raise KarnError("model_server_not_ready")
            time.sleep(1)

    def __exit__(self, *_):
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=30)


def _usage(usage: Any) -> dict[str, int | None] | None:
    """Chat-completions usage in the record's token keys. llama.cpp bills no cache writes and
    does not split reasoning tokens out of ``completion_tokens``."""
    if not isinstance(usage, dict):
        return None
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}

    def count(value):
        return (
            value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        )

    return {
        "input_tokens": count(usage.get("prompt_tokens")),
        "cached_input_tokens": count(prompt_details.get("cached_tokens")),
        "cache_write_input_tokens": 0,
        "output_tokens": count(usage.get("completion_tokens")),
        "reasoning_output_tokens": count(completion_details.get("reasoning_tokens")),
        "total_tokens": count(usage.get("total_tokens")),
    }


class _Response:
    """What one completion said, assembled from a stream or read whole."""

    def __init__(self):
        self.response_id = self.model = self.finish_reason = None
        self.usage = self.timings = None
        self.usage_reports = 0
        self.content: list[str] = []
        self.reasoning: list[str] = []
        self.tool_calls: dict[int, dict[str, Any]] = {}
        self._pending = b""

    def feed_stream(self, chunk: bytes) -> None:
        lines = (self._pending + chunk).split(b"\n")
        self._pending = lines.pop()
        for line in lines:
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                continue
            with contextlib.suppress(ValueError, RecursionError):
                self.ingest(json.loads(payload), delta=True)

    def ingest(self, document: Any, *, delta: bool) -> None:
        if not isinstance(document, dict):
            return
        self.response_id = document.get("id") or self.response_id
        self.model = document.get("model") or self.model
        if document.get("usage") is not None:
            self.usage = document["usage"]
            self.usage_reports += 1
        if isinstance(document.get("timings"), dict):
            self.timings = document["timings"]
        for choice in document.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            self.finish_reason = choice.get("finish_reason") or self.finish_reason
            message = choice.get("delta" if delta else "message") or {}
            if not isinstance(message, dict):
                continue
            if isinstance(message.get("content"), str):
                self.content.append(message["content"])
            if isinstance(message.get("reasoning_content"), str):
                self.reasoning.append(message["reasoning_content"])
            for position, call in enumerate(message.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                index = call.get("index", position) if delta else position
                row = self.tool_calls.setdefault(index, {"id": None, "name": "", "arguments": ""})
                row["id"] = call.get("id") or row["id"]
                function = call.get("function") or {}
                row["name"] += function.get("name") or ""
                row["arguments"] += function.get("arguments") or ""

    def message(self) -> dict[str, Any]:
        return {
            "content": "".join(self.content),
            "reasoning": "".join(self.reasoning),
            "tool_calls": [self.tool_calls[key] for key in sorted(self.tool_calls)],
        }


def _kept(value: Any, limit: int) -> Any:
    """Workload-controlled content as kept in the run's files: whole, or cut to ``limit``."""
    text = json.dumps(value, sort_keys=True, default=str)
    if len(text) <= limit:
        return value
    return {"truncated_from_chars": len(text), "head": text[:limit]}


def _new_messages(request: dict) -> Any:
    """The messages after the last assistant turn: what the agent added since its last reply."""
    messages = request.get("messages")
    if not isinstance(messages, list):
        return []
    added = messages
    for position in range(len(messages) - 1, -1, -1):
        if isinstance(messages[position], dict) and messages[position].get("role") == "assistant":
            added = messages[position + 1 :]
            break
    return _kept(added, MAX_KEPT_MESSAGES_CHARS)


class ModelRelayCollector:
    """Holds the host's model-server lock, starts the server, and relays and records requests.

    The relay listens on ``bind_host`` under a secret path, which only the run's proxy
    sidecar is given; the server itself listens on loopback only.
    """

    adapter = TELEMETRY_ADAPTER

    def __init__(self, run_dir: Path, *, plan: ModelServerPlan, bind_host: str = "127.0.0.1"):
        self.run_dir, self.plan, self.bind_host = Path(run_dir), plan, bind_host
        self.path = "/model/" + secrets.token_hex(16)
        self.events: list[dict[str, Any]] = []
        self.reasons: list[str] = []
        self.facts: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._exit = contextlib.ExitStack()
        self._server = self._thread = None
        self._sink = self._transcript = None
        self.llama: LlamaServer | None = None

    def __enter__(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._hold_host_lock()
            started = time.monotonic()
            if file_sha256(self.plan.model_path) != self.plan.spec.model_sha256:
                raise KarnError("model_digest_mismatch")
            self.facts = {
                **self.plan.to_dict(),
                "model_sha256_verified": True,
                "model_bytes": self.plan.model_path.stat().st_size,
                "verify_seconds": round(time.monotonic() - started, 3),
            }
            self._sink = self._exit.enter_context(self._open(EVENTS_FILE))
            self._transcript = self._exit.enter_context(self._open(TRANSCRIPT_FILE))
            started = time.monotonic()
            self.llama = self._exit.enter_context(LlamaServer(self.plan, self.run_dir / SERVER_LOG))
            self.facts["ready_seconds"] = round(time.monotonic() - started, 3)
            self._start_relay()
        except BaseException:
            self._exit.close()
            raise
        return self

    def _hold_host_lock(self):
        self.plan.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._exit.enter_context(self.plan.lock_path.open("a"))
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise KarnError("model_server_busy") from None

    def _open(self, name: str):
        fd = os.open(
            self.run_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        return os.fdopen(fd, "w", encoding="utf-8")

    @property
    def endpoint(self) -> str:
        if self._server is None:
            raise RuntimeError("relay_not_started")
        return f"http://{self.bind_host}:{self._server.server_port}{self.path}"

    def mark_incomplete(self, reason: str) -> None:
        with self._lock:
            self.reasons.append(reason)

    def harvest_native(self, native_state: Path) -> None:
        """A model-server run has no native journals; the relay saw every request."""

    def _write(self, sink, row: dict[str, Any]) -> None:
        with self._lock:
            if sink is not None and not sink.closed:
                sink.write(json.dumps(row, sort_keys=True) + "\n")
                sink.flush()

    def record(self, event: dict[str, Any], transcript: dict[str, Any] | None) -> None:
        with self._lock:
            self.events.append(event)
            self._write(self._sink, event)
            if transcript is not None:
                self._write(self._transcript, transcript)

    def _start_relay(self):
        collector = self

        class Relay(BaseHTTPRequestHandler):
            # HTTP/1.0: each response ends when the relay closes, so a stream needs no framing.
            protocol_version = "HTTP/1.0"
            # Reading a request; the sidecar sends each one whole.
            timeout = 300

            def log_message(self, *args):
                pass

            def do_GET(self):
                collector.relay(self)

            def do_POST(self):
                collector.relay(self)

        self._server = ThreadingHTTPServer((self.bind_host, 0), Relay)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._exit.callback(self._stop_relay)

    def relay(self, handler: BaseHTTPRequestHandler) -> None:
        if not handler.path.startswith(self.path + "/"):
            handler.send_error(404)
            return
        target = handler.path[len(self.path) :]
        if (handler.command, target) not in RELAYED_PATHS:
            handler.send_error(404)
            return
        length = handler.headers.get("Content-Length") or "0"
        if not length.isdigit() or int(length) > MAX_REQUEST_BYTES:
            handler.send_error(413)
            return
        body = handler.rfile.read(int(length))
        if handler.command == "GET":
            self._forward(handler, target, body, None)
            return
        try:
            request = json.loads(body)
        except (ValueError, RecursionError):
            handler.send_error(400)
            return
        request = request if isinstance(request, dict) else {}
        # Several choices in one stream would each report usage; pi asks for one.
        if request.get("n", 1) != 1:
            handler.send_error(400)
            return
        self._forward(handler, target, body, request)

    def _forward(self, handler, target: str, body: bytes, request: dict | None) -> None:
        started_ms = int(time.time() * 1000)
        response, status, error = _Response(), None, None
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.llama.port, timeout=UPSTREAM_TIMEOUT_SECONDS
        )
        try:
            headers = {"Content-Type": "application/json"} if body else {}
            connection.request(handler.command, target, body or None, headers)
            upstream = connection.getresponse()
            status = upstream.status
            handler.send_response(status)
            kind = upstream.getheader("Content-Type", "application/json")
            handler.send_header("Content-Type", kind)
            handler.send_header("Cache-Control", "no-cache")
            handler.end_headers()
            streaming = kind.startswith("text/event-stream")
            whole = []
            while chunk := upstream.read1(65536):
                if streaming:
                    response.feed_stream(chunk)
                elif request is not None:
                    whole.append(chunk)
                try:
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
                except OSError:
                    error = "client_disconnected"
                    break
            if whole:
                with contextlib.suppress(ValueError, RecursionError):
                    response.ingest(json.loads(b"".join(whole)), delta=False)
        except (OSError, http.client.HTTPException) as failure:
            error = error or "upstream_failed:" + type(failure).__name__
            if status is None:
                with contextlib.suppress(OSError):
                    handler.send_error(502)
        finally:
            connection.close()
        if request is None:
            return
        # One event per relayed request, whatever ids the server reuses.
        identity = "relay-" + uuid.uuid4().hex
        try:
            self._observe(identity, request, response, status, error, started_ms)
        except Exception:  # noqa: BLE001 -- a request the server saw is never left unrecorded.
            self.record(
                {
                    "id": identity,
                    "kind": "response",
                    "response_id": identity,
                    "status": status,
                    "error": "observation_failed",
                    "usage": None,
                    "timestamp_ms": started_ms,
                },
                None,
            )

    def _observe(self, identity, request, response: _Response, status, error, started_ms):
        message = response.message()
        messages = request.get("messages")
        overrides = sorted(set(request) - ORDINARY_REQUEST_KEYS)
        event = {
            "id": identity,
            "kind": "response",
            "response_id": _kept(response.response_id, 256) or identity,
            "thread_id": THREAD_ID,
            "model": _kept(response.model, 256),
            "requested_model": _kept(request.get("model"), 256),
            "request_parameters": _kept(
                {key: request[key] for key in overrides}, MAX_KEPT_FIELD_CHARS
            ),
            "status": status,
            "error": error,
            "finish_reason": _kept(response.finish_reason, 64),
            "usage": _usage(response.usage),
            "usage_reports": response.usage_reports,
            "timings": _kept(response.timings, MAX_KEPT_FIELD_CHARS),
            "tool_calls": len(message["tool_calls"]),
            "stream": bool(request.get("stream")),
            "max_completion_tokens": _kept(request.get("max_completion_tokens"), 64),
            "request_messages": len(messages) if isinstance(messages, list) else None,
            "timestamp_ms": started_ms,
            "completed_ms": int(time.time() * 1000),
        }
        transcript = {
            "id": identity,
            "response_id": event["response_id"],
            "timestamp_ms": started_ms,
            "new_messages": _new_messages(request),
            "response": _kept(message, MAX_KEPT_MESSAGES_CHARS),
            "finish_reason": response.finish_reason,
            "status": status,
            "error": error,
        }
        self.record(event, transcript)

    def finalize(self, *, exit_kind: str, native_version: str | None = None) -> dict[str, Any]:
        self._stop_relay()
        with self._lock:
            result = summarize_model_events(
                self.events, exit_kind=exit_kind, collection_reasons=self.reasons
            )
            fd = os.open(
                self.run_dir / "observations.json",
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(result, output, sort_keys=True, indent=2)
                output.write("\n")
            return result

    def _stop_relay(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5)
            self._server = None

    def __exit__(self, *_):
        self._exit.close()


def _sum(rows, key):
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    return sum(values) if values else 0


def server_timings(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Throughput over every completed request, from the server's own ``timings``."""
    timings = [row["timings"] for row in rows if isinstance(row.get("timings"), dict)]
    prompt_ms, generation_ms = _sum(timings, "prompt_ms"), _sum(timings, "predicted_ms")
    prompt, generated = _sum(timings, "prompt_n"), _sum(timings, "predicted_n")
    return {
        "requests_with_timings": len(timings),
        "prompt_tokens_processed": prompt,
        "prompt_cache_tokens": _sum(timings, "cache_n"),
        "generated_tokens": generated,
        "prompt_seconds": round(prompt_ms / 1000, 3),
        "generation_seconds": round(generation_ms / 1000, 3),
        "prompt_tokens_per_second": round(prompt * 1000 / prompt_ms, 3) if prompt_ms else None,
        "generation_tokens_per_second": (
            round(generated * 1000 / generation_ms, 3) if generation_ms else None
        ),
    }


def summarize_model_events(events, *, exit_kind: str, collection_reasons=()) -> dict[str, Any]:
    """Measurements from the relay's events.

    Every request reaches one server, so the relay cannot tell a second agent process from
    the main one: subagent use is unknown, never ``none``.
    """
    reasons = list(collection_reasons)
    unique: dict[str, dict[str, Any]] = {}
    for event in events:
        if isinstance(event, dict) and event.get("kind") == "response" and event.get("id"):
            unique.setdefault(event["id"], event)
    rows = sorted(unique.values(), key=lambda row: row.get("timestamp_ms") or 0)
    completed = [row for row in rows if row.get("status") == 200 and not row.get("error")]
    failed = len(rows) - len(completed)
    if failed:
        # The server may have done the work of a request whose usage never reached the relay.
        reasons.append("relayed_request_incomplete")
    if any((row.get("usage_reports") or 0) > 1 for row in completed):
        reasons.append("multiple_usage_reports")
    requests = []
    for row in completed:
        usage = row.get("usage")
        if usage is None:
            reasons.append("response_usage_missing")
            usage = dict.fromkeys(TOKEN_KEYS)
        requests.append(
            {
                "response_id": row["response_id"],
                "thread_id": THREAD_ID,
                "model": row.get("model"),
                "usage": usage,
                "timestamp_ms": row.get("timestamp_ms"),
                "compaction": False,
                "finish_reason": row.get("finish_reason"),
                "timings": row.get("timings"),
            }
        )
    if exit_kind != "completed":
        reasons.append("execution_did_not_complete")
    measurements = _measurements(
        requests,
        len(completed),
        sum(row.get("tool_calls") or 0 for row in completed),
        reasons,
        True,
        {
            "source": TELEMETRY_ADAPTER,
            "relayed_requests": len(rows),
            "failed_requests": failed,
            "requests_with_parameter_overrides": sum(
                1 for row in rows if row.get("request_parameters")
            ),
        },
        subagent_threads=None,
        subagents=None,
        subagents_reason="threads_not_observable",
    )
    measurements["server_timings"] = server_timings(completed)
    return measurements
