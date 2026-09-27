"""Sanitized native Codex observations and an opt-in OTLP/JSON receiver.

Harvest the fresh native home's sessions after container stop and before the
login exit hook clears them. Per-response usage records, never cumulative
parent/turn totals, own accounting. HTTP logs supplement interrupted journals.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import threading
from collections import defaultdict, deque
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .pricing import price_requests, price_table_metadata

QUALIFIED_CODEX_VERSION = "0.153.4"
TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)
_OTLP_TOKENS = dict(
    zip(
        TOKEN_KEYS,
        (
            "input_token_count",
            "cached_token_count",
            "cache_write_token_count",
            "output_token_count",
            "reasoning_token_count",
            "tool_token_count",
        ),
        strict=True,
    )
)
_EVENTS = {
    "codex.conversation_starts",
    "codex.api_request",
    "codex.sse_event",
    "codex.websocket_event",
    "codex.tool_decision",
    "codex.tool_result",
}
_ATTRIBUTES = {
    "event.name",
    "event.kind",
    "event.timestamp",
    "conversation.id",
    "app.version",
    "model",
    "slug",
    "call_id",
    "tool_name",
    "tool_namespace",
    "tool_result_seq",
    "success",
    "attempt",
    "endpoint",
    "http.response.status_code",
    "agent_name",
    "reasoning_effort",
    "model_reasoning_effort",
    *_OTLP_TOKENS.values(),
}
_TOOL_TYPES = {
    "function_call",
    "custom_tool_call",
    "local_shell_call",
    "web_search_call",
    "computer_call",
    "file_search_call",
    "code_interpreter_call",
    "mcp_call",
}
_SAFE = re.compile(r"[A-Za-z0-9_./:@+-]{1,256}\Z")


def _label(value: Any) -> str | None:
    return value if isinstance(value, str) and _SAFE.fullmatch(value) else None


def _integer(value: Any) -> int | None:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value):
        value = int(value)
    return value if type(value) is int and 0 <= value < 2**64 else None


def _stamp(value: Any) -> int:
    if not isinstance(value, str):
        return 0
    try:
        return int(datetime.fromisoformat(value).timestamp() * 1000)
    except (ValueError, OverflowError):
        return 0


def _usage(value: Any) -> dict[str, int | None]:
    value = value if isinstance(value, dict) else {}
    return {key: _integer(value.get(key)) for key in TOKEN_KEYS}


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def normalize_otlp(payload: Any) -> list[dict[str, Any]]:
    """Discard prompts, tool arguments/output, identities and authentication metadata."""
    result = []
    if not isinstance(payload, dict) or not isinstance(payload.get("resourceLogs"), list):
        raise TypeError("invalid_otlp_envelope")
    for resource in payload["resourceLogs"]:
        for scope in resource.get("scopeLogs", []):
            for record in scope.get("logRecords", []):
                attrs = {}
                for entry in record.get("attributes", []):
                    key = entry.get("key")
                    if key not in _ATTRIBUTES:
                        continue
                    raw = entry.get("value", {})
                    value = next(
                        (raw[k] for k in ("stringValue", "intValue", "boolValue") if k in raw), None
                    )
                    if isinstance(value, bool) or _label(value) is not None:
                        attrs[key] = value
                if attrs.get("event.name") not in _EVENTS:
                    continue
                if attrs["event.name"] in (
                    "codex.sse_event",
                    "codex.websocket_event",
                ) and attrs.get("event.kind") not in {
                    "response.created",
                    "response.completed",
                    "response.failed",
                    "response.incomplete",
                    "error",
                }:
                    continue
                event = {
                    "source": "otel",
                    "kind": attrs["event.name"],
                    "thread_id": attrs.get("conversation.id"),
                    "timestamp_ms": _stamp(attrs.get("event.timestamp")),
                    "observed_ns": _integer(record.get("observedTimeUnixNano")),
                    "attributes": attrs,
                }
                event["id"] = "otel:" + _fingerprint(event)
                result.append(event)
    return result


def normalize_rollout(lines: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract only accounting fields; never retain native messages or payload text."""
    events: list[dict[str, Any]] = []
    problems: list[str] = []
    thread_id = model = version = None
    birth_ms = 0
    active = False

    def emit(kind: str, key: str, timestamp: Any, **fields: Any) -> None:
        events.append(
            {
                "source": "native",
                "kind": kind,
                "id": key,
                "thread_id": thread_id,
                "timestamp_ms": _stamp(timestamp),
                **fields,
            }
        )

    def usage_record(payload: dict[str, Any], timestamp: Any) -> None:
        response = _label(payload.get("response_id"))
        owner = _label(payload.get("thread_id")) or thread_id
        if not response or not owner:
            problems.append("native_response_identity_missing")
            return
        emit(
            "response",
            "response:" + response,
            timestamp,
            response_id=response,
            owner_thread_id=owner,
            model=model,
            usage=_usage(payload.get("usage")),
        )

    for line in lines:
        try:
            record = json.loads(line)
            payload = record.get("payload", {})
            if not isinstance(payload, dict):
                raise TypeError
        except (ValueError, TypeError, AttributeError):
            problems.append("native_record_malformed")
            continue
        kind, timestamp = record.get("type"), record.get("timestamp")
        if kind == "session_meta" and thread_id is not None:
            continue
        if birth_ms and _stamp(timestamp) < birth_ms:
            continue
        if kind == "session_meta":
            birth_ms = _stamp(timestamp)
            thread_id = _label(payload.get("id"))
            version = _label(payload.get("cli_version"))
            emit(
                "session", "session:" + (thread_id or "unknown"), timestamp, native_version=version
            )
        elif kind == "turn_context":
            model = _label(payload.get("model"))
            active = True
        elif kind == "token_usage_record":
            usage_record(payload, timestamp)
        elif kind == "compacted":
            response = _label(payload.get("compaction_response_id"))
            if response:
                emit("compaction", "compaction:" + response, timestamp, response_id=response)
            latest = payload.get("latest_token_usage_record")
            if isinstance(latest, dict):
                usage_record(latest, timestamp)
            if not response and not isinstance(latest, dict):
                problems.append("compaction_response_identity_missing")
        elif kind == "response_item" and active and payload.get("type") in _TOOL_TYPES:
            call = _label(payload.get("call_id")) or _label(payload.get("id"))
            if call:
                origin = (
                    _label(
                        payload.get("internal_chat_message_metadata_passthrough", {}).get("turn_id")
                    )
                    or thread_id
                )
                emit(
                    "tool_call",
                    "tool:" + (origin or "unknown") + ":" + call,
                    timestamp,
                    call_id=call,
                    tool_name=_label(payload.get("name")) or payload["type"],
                )
            else:
                problems.append("native_tool_identity_missing")
        elif kind == "event_msg":
            event_type = payload.get("type")
            turn = _label(payload.get("turn_id"))
            if event_type in ("task_started", "task_complete", "turn_aborted") and turn:
                if event_type == "task_started":
                    active = True
                emit(
                    event_type,
                    event_type + ":" + (thread_id or "unknown") + ":" + turn,
                    timestamp,
                    turn_id=turn,
                )
    if not thread_id:
        problems.append("native_session_identity_missing")
    return events, sorted(set(problems))


def _measurement(value: Any, reasons: Iterable[str], *, present: bool) -> dict[str, Any]:
    reasons = sorted(set(reasons))
    return {
        "value": value if present else None,
        "completeness": "missing" if not present else "partial" if reasons else "complete",
        "reasons": reasons,
    }


def summarize_events(
    events: Iterable[dict[str, Any]], *, exit_kind: str, collection_reasons: Iterable[str] = ()
) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    reasons = list(collection_reasons)
    for event in events:
        previous = unique.get(event["id"])
        if previous is not None and event["kind"] == "response":
            comparable = ("response_id", "owner_thread_id", "model", "usage")
            if any(previous.get(key) != event.get(key) for key in comparable):
                reasons.append("conflicting_response_observations")
            continue
        unique.setdefault(event["id"], event)
    rows = list(unique.values())
    sessions = [e for e in rows if e["kind"] == "session"]
    requests = [
        {
            "response_id": e["response_id"],
            "thread_id": e["owner_thread_id"],
            "model": e.get("model"),
            "usage": e["usage"],
            "timestamp_ms": e["timestamp_ms"],
        }
        for e in rows
        if e["kind"] == "response"
    ]
    compactions = {e["response_id"] for e in rows if e["kind"] == "compaction"}
    for request in requests:
        request["compaction"] = request["response_id"] in compactions
    native_threads = {e["thread_id"] for e in sessions}
    otel_threads = set()
    tools = {e["id"] for e in rows if e["kind"] == "tool_call"}
    native_calls = {e["call_id"] for e in rows if e["kind"] == "tool_call"}
    starts = []
    otel_usage = []
    versions = {e.get("native_version") for e in sessions}
    for event in rows:
        if event["source"] != "otel":
            continue
        attrs = event["attributes"]
        owner = event.get("thread_id")
        if owner:
            otel_threads.add(owner)
        if attrs.get("app.version"):
            versions.add(attrs["app.version"])
        if (
            event["kind"] in ("codex.sse_event", "codex.websocket_event")
            and attrs.get("event.kind") == "response.created"
        ):
            starts.append(event)
        if (
            event["kind"] in ("codex.tool_decision", "codex.tool_result")
            and attrs.get("call_id")
            and attrs["call_id"] not in native_calls
        ):
            tools.add("otel-tool:" + str(owner) + ":" + attrs["call_id"])
        if (
            event["kind"] in ("codex.sse_event", "codex.websocket_event")
            and attrs.get("event.kind") == "response.completed"
            and "input_token_count" in attrs
        ):
            otel_usage.append(event)
    native_usage_threads = {r["thread_id"] for r in requests}
    for event in otel_usage:
        if event["thread_id"] in native_usage_threads:
            continue
        attrs = event["attributes"]
        requests.append(
            {
                "response_id": event["id"],
                "thread_id": event["thread_id"],
                "model": attrs.get("model"),
                "timestamp_ms": event["timestamp_ms"],
                "usage": {key: _integer(attrs.get(source)) for key, source in _OTLP_TOKENS.items()},
                "compaction": False,
                "response_identity": "otel_observation",
            }
        )
        reasons.append("native_usage_unavailable_for_observed_thread")
    if not sessions:
        reasons.append("native_journals_unavailable")
    if otel_threads - native_threads:
        reasons.append("native_journal_missing_for_observed_thread")
    if versions != {QUALIFIED_CODEX_VERSION}:
        reasons.append("native_version_not_qualified")
    opened = {e["turn_id"] for e in rows if e["kind"] == "task_started"}
    closed = {e["turn_id"] for e in rows if e["kind"] == "task_complete"}
    if opened - closed:
        reasons.append("native_turn_not_completed")
    if exit_kind != "completed":
        reasons.append("execution_did_not_complete")
    present = bool(sessions or otel_threads)

    # OTel response starts supply a lower bound for an interrupted response
    # without a final usage record. Native records include remote compaction,
    # whose requests are absent from this version's OTel stream.
    pending: dict[str, deque] = defaultdict(deque)
    timeline = [(e["timestamp_ms"], 0, e) for e in starts]
    timeline += [(r["timestamp_ms"], 1, r) for r in requests]
    for _, kind, item in sorted(timeline, key=lambda item: (item[0], item[1])):
        owner = item.get("thread_id")
        if kind == 0:
            pending[owner].append(item)
        elif pending[owner]:
            pending[owner].popleft()
    unresolved = sum(len(value) for value in pending.values())
    if unresolved:
        reasons.append("response_started_without_native_usage")
    response_count = len(requests) + unresolved
    if not requests and otel_usage:
        response_count = max(response_count, len(otel_usage))
    if present and not opened:
        reasons.append("native_turn_start_unobserved")
    observed_zero = present and not response_count and not reasons
    turn_reasons = list(reasons)
    usage_reasons = list(reasons)
    totals = {}
    for key in TOKEN_KEYS:
        values = [r["usage"].get(key) for r in requests]
        observed = [v for v in values if v is not None]
        if len(observed) != len(values):
            usage_reasons.append("missing_" + key)
        totals[key] = sum(observed) if observed else (0 if observed_zero else None)
    priced = price_requests(requests)
    priced_values = [Decimal(r["usd"]) for r in priced if r["usd"] is not None]
    cost_reasons = list(reasons) + [why for row in priced for why in row["reasons"]]
    if response_count and not requests:
        usage_reasons.append("per_response_usage_unavailable")
        cost_reasons.append("per_response_usage_unavailable")
    costs_present = bool(priced_values) or observed_zero
    result = {
        "schema_version": 1,
        "agent_turns": {
            "responses": _measurement(response_count, turn_reasons, present=present),
            "tool_calls": _measurement(len(tools), turn_reasons, present=present),
            "total": _measurement(response_count + len(tools), turn_reasons, present=present),
        },
        "usage": _measurement(totals, usage_reasons, present=bool(requests) or observed_zero),
        "estimated_cost": _measurement(
            format(sum(priced_values, Decimal(0)), "f"), cost_reasons, present=costs_present
        ),
        "requests": requests,
        "request_prices": priced,
        "price_table": price_table_metadata(),
        "coverage": {
            "native_versions": sorted(v for v in versions if v),
            "native_threads": len(native_threads),
            "observed_threads": len(otel_threads | native_threads),
            "remote_or_local_compactions": len(compactions),
            "deduplicated_events": len(rows),
            "exit_kind": exit_kind,
            "model_basis": "native_turn_context; observation, not provider attestation",
        },
    }
    return result


class CodexTelemetryCollector:
    """Host-owned receiver; the workload sees only its POST-only telemetry route."""

    def __init__(
        self,
        run_dir: Path,
        *,
        bind_host: str = "127.0.0.1",
        port: int = 0,
        max_body_bytes: int = 4 * 1024 * 1024,
    ):
        self.run_dir = Path(run_dir)
        self.bind_host, self.port = bind_host, port
        self.max_body_bytes = max_body_bytes
        self.path = "/v1/logs/" + secrets.token_hex(16)
        self.events: list[dict[str, Any]] = []
        self.reasons: list[str] = []
        self._lock = threading.RLock()
        self._server = self._thread = None
        self._sink = None
        self._seen: set[str] = set()

    def __enter__(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            self.run_dir / "observations.events.jsonl",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        self._sink = os.fdopen(fd, "w", encoding="utf-8")
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.path != collector.path:
                    self.send_error(404)
                    return
                length = _integer(self.headers.get("Content-Length"))
                if length is None or length > collector.max_body_bytes:
                    collector.mark_incomplete("otel_request_size_invalid")
                    self.send_error(413)
                    return
                try:
                    collector.ingest_otlp(json.loads(self.rfile.read(length)))
                except (ValueError, TypeError, KeyError, AttributeError):
                    collector.mark_incomplete("otel_payload_malformed")
                    self.send_error(400)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

        try:
            self._server = ThreadingHTTPServer((self.bind_host, self.port), Handler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        except BaseException:
            self._sink.close()
            raise
        return self

    @property
    def endpoint(self) -> str:
        if self._server is None:
            raise RuntimeError("collector_not_started")
        return f"http://{self.bind_host}:{self._server.server_port}{self.path}"

    def config_toml(self, endpoint: str | None = None) -> str:
        selected = endpoint or self.endpoint
        parsed = urlsplit(selected)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("invalid_telemetry_endpoint")
        return (
            '[otel]\nenvironment = "silverquillm-benchmark"\n'
            'log_user_prompt = false\nmetrics_exporter = "none"\ntrace_exporter = "none"\n'
            "exporter = { otlp-http = { endpoint = "
            + json.dumps(selected)
            + ', protocol = "json" } }\n'
        )

    def mark_incomplete(self, reason: str) -> None:
        with self._lock:
            self.reasons.append(reason)

    def _append(self, event: dict[str, Any]) -> None:
        with self._lock:
            if event["id"] in self._seen and event["kind"] != "response":
                return
            self._seen.add(event["id"])
            self.events.append(event)
            if self._sink is not None:
                self._sink.write(json.dumps(event, sort_keys=True) + "\n")
                self._sink.flush()

    def ingest_otlp(self, payload: dict[str, Any]) -> None:
        for event in normalize_otlp(payload):
            self._append(event)

    def harvest_native(self, native_state: Path, *, max_bytes: int = 128 * 1024 * 1024) -> None:
        """Read sessions only, never auth.json, before Karn's login harvest removes them."""
        root = Path(native_state) / "sessions"
        if root.is_symlink() or not root.is_dir():
            self.mark_incomplete("native_sessions_unavailable")
            return
        consumed, files = 0, 0
        for directory, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
            for name in sorted(names):
                if not name.startswith("rollout-") or not name.endswith(".jsonl"):
                    continue
                try:
                    fd = os.open(
                        Path(directory) / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                    )
                    with os.fdopen(fd, "rb") as source:
                        info = os.fstat(source.fileno())
                        if not stat.S_ISREG(info.st_mode) or consumed + info.st_size > max_bytes:
                            self.mark_incomplete("native_journal_size_or_type_invalid")
                            continue
                        content = source.read(max_bytes - consumed + 1)
                    consumed += len(content)
                    if consumed > max_bytes:
                        self.mark_incomplete("native_journal_size_limit")
                        return
                    rows, problems = normalize_rollout(content.decode("utf-8").splitlines())
                    for row in rows:
                        self._append(row)
                    for problem in problems:
                        self.mark_incomplete(problem)
                    files += 1
                except (OSError, UnicodeError):
                    self.mark_incomplete("native_journal_unreadable")
        if not files:
            self.mark_incomplete("native_journals_unavailable")

    def finalize(self, *, exit_kind: str, native_version: str | None = None) -> dict[str, Any]:
        if native_version is not None and native_version != QUALIFIED_CODEX_VERSION:
            self.mark_incomplete("native_version_not_qualified")
        self._stop_receiver()
        with self._lock:
            result = summarize_events(
                self.events, exit_kind=exit_kind, collection_reasons=self.reasons
            )
            path = self.run_dir / "observations.json"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(result, output, sort_keys=True, indent=2)
                output.write("\n")
            return result

    def _stop_receiver(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5)
            self._server = None

    def __exit__(self, *args):
        self._stop_receiver()
        if self._sink is not None:
            self._sink.close()
            self._sink = None
