"""Sanitized native Claude Code observations: session transcripts plus an OTel cross-check.

The transcript under the config directory is the durable source, harvested after container
stop and before the login plugin clears its work directory; recovery reads the same copy.
Claude Code writes one transcript line per content block of an assistant message, each
repeating the message's usage, so accounting is keyed by message id. A compaction's own
request never appears in the transcript; its OTel ``api_request`` supplies the usage.
Every other ``api_request`` is reconciled against its transcript response: a disagreement
leaves the transcript's values in place and marks the observations partial.
"""

from __future__ import annotations

import io
import json
import os
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any

from silverquillm.safe_files import TreeLimitExceeded, iter_regular_files, open_directory

from .observations import (
    CodexTelemetryCollector,
    _fingerprint,
    _integer,
    _measurements,
    _stamp,
)

# Versions whose transcript and OTel streams were checked against each other on a real run.
QUALIFIED_CLAUDE_VERSIONS: frozenset[str] = frozenset({"2.1.284"})
MAX_TRANSCRIPT_BYTES = 128 * 1024 * 1024
MAX_TRANSCRIPT_FILES = 10_000
MAX_REQUEST_COST_USD = Decimal(1_000_000)
_EVENTS = {"claude_code.api_request", "claude_code.tool_result", "claude_code.api_error"}
_FINISHED = {"end_turn", "stop_sequence"}
# Claude Code's OTel reports the API's "standard" usage speed as "normal".
_OTEL_SPEEDS = {"normal": "standard"}
# The usage fields both streams report; OTel carries no 1-hour cache-write split.
COMPARED_USAGE = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
)

# The real shapes of every label a Claude run can contribute to a record, checked against
# Claude Code transcripts. The workload writes these files and can steer its OTel, so any
# other value, such as a token copied into an id, is dropped and flagged, never retained.
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_COUNT = r"[0-9]{1,20}"
SHAPES = {
    "session": re.compile(_UUID),
    "agent": re.compile(r"a[0-9a-f]{8,32}"),
    "uuid": re.compile(_UUID),
    "message": re.compile(r"msg_[A-Za-z0-9]{1,64}"),
    "request": re.compile(r"req_[A-Za-z0-9]{1,64}"),
    "tool_use": re.compile(r"toolu_[A-Za-z0-9]{1,64}"),
    "tool_name": re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}"),
    "version": re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,6}"),
    "model": re.compile(r"claude-[a-z0-9-]{1,64}"),
    "speed": re.compile(r"standard|fast|normal"),
    "service_tier": re.compile(r"standard|priority|batch"),
    "stop_reason": re.compile(r"[a-z_]{1,32}"),
    "timestamp": re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]{8,15}(Z|[+-][0-9]{2}:[0-9]{2})"),
    "count": re.compile(_COUNT),
    "cost": re.compile(r"[0-9]{1,12}(\.[0-9]{1,20})?"),
}
# Identity attributes (user.email, user.account_uuid, organization.id, ...), prompts, tool
# arguments and free-form names are never retained; each kept attribute has a shape.
_ATTRIBUTES = {
    "event.name": None,
    "event.timestamp": "timestamp",
    "event.sequence": "count",
    "session.id": "session",
    "app.version": "version",
    "model": "model",
    "request_id": "request",
    "query_source": None,
    "speed": "speed",
    "input_tokens": "count",
    "output_tokens": "count",
    "cache_read_tokens": "count",
    "cache_creation_tokens": "count",
    "cost_usd": "cost",
    "duration_ms": "count",
    "tool_name": "tool_name",
    "tool_use_id": "tool_use",
    "success": None,
    "status_code": "count",
    "attempt": "count",
}
# query_source names subagents, which the workload can define; only these values are kept.
_QUERY_SOURCES = {"repl_main_thread", "compact"}


def _shaped(value: Any, shape: str, problems: list[str]) -> str | None:
    """``value`` when it has the label's real shape; anything else is dropped and flagged."""
    if value is None:
        return None
    if isinstance(value, str) and SHAPES[shape].fullmatch(value):
        return value
    problems.append("native_label_rejected")
    return None


def _known(value: Any, shape: str, problems: list[str]) -> str | None:
    """An enumerated label; an unrecognized value becomes "unknown", which stays unpriced."""
    if value is None:
        return None
    return _shaped(value, shape, problems) or "unknown"


def claude_usage(value: Any) -> dict[str, int | None]:
    """Anthropic usage in the bench convention: input includes cache reads and writes."""
    value = value if isinstance(value, dict) else {}
    uncached = _integer(value.get("input_tokens"))
    read = _integer(value.get("cache_read_input_tokens"))
    written = _integer(value.get("cache_creation_input_tokens"))
    output = _integer(value.get("output_tokens"))
    split = value.get("cache_creation")
    written_1h = None
    if isinstance(split, dict):
        short = _integer(split.get("ephemeral_5m_input_tokens"))
        long = _integer(split.get("ephemeral_1h_input_tokens"))
        if short is not None and long is not None and short + long == written:
            written_1h = long
    elif written == 0:
        written_1h = 0
    details = value.get("output_tokens_details")
    reasoning = _integer(details.get("thinking_tokens")) if isinstance(details, dict) else None
    known = None not in (uncached, read, written)
    total_input = uncached + read + written if known else None
    return {
        "input_tokens": total_input,
        "cached_input_tokens": read,
        "cache_write_input_tokens": written,
        "cache_write_1h_input_tokens": written_1h,
        "output_tokens": output,
        "reasoning_output_tokens": reasoning,
        "total_tokens": (
            total_input + output if total_input is not None and output is not None else None
        ),
    }


def normalize_transcript(lines: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract only accounting fields from one transcript; never retain message content."""
    problems: list[str] = []
    events: list[dict[str, Any]] = []
    responses: dict[str, dict[str, Any]] = {}
    tools: dict[str, dict[str, Any]] = {}
    thread = version = None
    sidechain = False
    started = False
    last_stop = None

    def base(kind: str, key: str, timestamp: Any, **fields: Any) -> dict[str, Any]:
        return {
            "source": "native",
            "kind": kind,
            "id": key,
            "thread_id": thread,
            "timestamp_ms": _stamp(timestamp),
            **fields,
        }

    for line in lines:
        try:
            record = json.loads(line)
            if not isinstance(record, dict):
                raise TypeError
        except (ValueError, TypeError, RecursionError):
            problems.append("native_record_malformed")
            continue
        kind, timestamp = record.get("type"), record.get("timestamp")
        if kind not in ("assistant", "user", "system"):
            continue
        if thread is None:
            sidechain = record.get("isSidechain") is True
            thread = (
                _shaped(record.get("agentId"), "agent", problems)
                if sidechain
                else _shaped(record.get("sessionId"), "session", problems)
            )
        version = version or _shaped(record.get("version"), "version", problems)
        if kind == "user" and not sidechain and not record.get("isMeta"):
            started = True
        elif kind == "system" and record.get("subtype") == "compact_boundary":
            boundary = _shaped(record.get("uuid"), "uuid", problems)
            if boundary:
                events.append(base("compaction", "compaction:" + boundary, timestamp))
            else:
                problems.append("compaction_identity_missing")
        elif kind == "assistant":
            message = record.get("message")
            if not isinstance(message, dict) or message.get("model") == "<synthetic>":
                continue
            response = _shaped(message.get("id"), "message", problems)
            if not response:
                problems.append("native_response_identity_missing")
                continue
            usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
            # Every block's line repeats the message; the last one carries its final state.
            responses[response] = base(
                "response",
                "response:" + response,
                timestamp,
                response_id=response,
                request_id=_shaped(record.get("requestId"), "request", problems),
                owner_thread_id=thread,
                model=_shaped(message.get("model"), "model", problems),
                usage=claude_usage(usage),
                speed=_known(usage.get("speed"), "speed", problems),
                service_tier=_known(usage.get("service_tier"), "service_tier", problems),
            )
            if not sidechain:
                last_stop = _shaped(message.get("stop_reason"), "stop_reason", problems)
            content = message.get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    call = _shaped(block.get("id"), "tool_use", problems)
                    if call:
                        tools[call] = base(
                            "tool_call",
                            "tool:" + call,
                            timestamp,
                            call_id=call,
                            tool_name=_shaped(block.get("name"), "tool_name", problems)
                            or "tool_use",
                        )
                    else:
                        problems.append("native_tool_identity_missing")
    if not thread:
        problems.append("native_session_identity_missing")
        return [], sorted(set(problems))
    session = base("session", "session:" + thread, None, native_version=version)
    rows = [session, *events, *responses.values(), *tools.values()]
    if not sidechain and started:
        rows.append(base("task_started", "task_started:" + thread, None, turn_id=thread))
        if last_stop in _FINISHED:
            rows.append(base("task_complete", "task_complete:" + thread, None, turn_id=thread))
    return rows, sorted(set(problems))


def _otel_value(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return None
    if "doubleValue" in raw:
        try:
            value = Decimal(repr(raw["doubleValue"]))
        except (InvalidOperation, TypeError):
            return None
        return format(value, "f") if value.is_finite() else None
    return next((raw[k] for k in ("stringValue", "intValue", "boolValue") if k in raw), None)


def normalize_claude_otlp(payload: Any, problems: list[str] | None = None) -> list[dict[str, Any]]:
    """Keep allowlisted Claude Code accounting events; drop identities, prompts and arguments."""
    problems = problems if problems is not None else []
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
                    value = _otel_value(entry.get("value", {}))
                    if type(value) is int:
                        value = str(value)
                    shape = _ATTRIBUTES[key]
                    if key == "success":
                        if isinstance(value, bool):
                            attrs[key] = value
                    elif key == "query_source":
                        attrs[key] = value if value in _QUERY_SOURCES else "other"
                    elif key == "event.name":
                        attrs[key] = value if isinstance(value, str) else None
                    elif (kept := _shaped(value, shape, problems)) is not None:
                        attrs[key] = kept
                name = attrs.get("event.name")
                if name is None:
                    body = record.get("body", {})
                    name = body.get("stringValue") if isinstance(body, dict) else None
                # The event is named with or without its claude_code prefix.
                if isinstance(name, str) and not name.startswith("claude_code."):
                    name = "claude_code." + name
                if name not in _EVENTS:
                    continue
                attrs["event.name"] = name
                event = {
                    "source": "otel",
                    "kind": name,
                    "thread_id": attrs.get("session.id"),
                    "timestamp_ms": _stamp(attrs.get("event.timestamp")),
                    "observed_ns": _integer(record.get("observedTimeUnixNano")),
                    "attributes": attrs,
                }
                event["id"] = "otel:" + _fingerprint(event)
                result.append(event)
    return result


def _otel_usage(attrs: dict[str, Any]) -> dict[str, int | None]:
    return claude_usage(
        {
            "input_tokens": attrs.get("input_tokens"),
            "cache_read_input_tokens": attrs.get("cache_read_tokens"),
            "cache_creation_input_tokens": attrs.get("cache_creation_tokens"),
            "output_tokens": attrs.get("output_tokens"),
        }
    )


def _reconcile(native: dict[str, Any], attrs: dict[str, Any], reasons: list[str]) -> None:
    """Compare one ``api_request`` with its transcript response, whose values stay authoritative."""
    observed = _otel_usage(attrs)
    for key in COMPARED_USAGE:
        mine = native["usage"].get(key)
        if mine is None or observed[key] is None:
            reasons.append("otel_usage_comparison_unavailable")
        elif mine != observed[key]:
            reasons.append("otel_usage_conflicts_with_native")
    if native.get("model") is None or attrs.get("model") is None:
        reasons.append("otel_model_comparison_unavailable")
    elif native["model"] != attrs["model"]:
        reasons.append("otel_model_conflicts_with_native")


def summarize_claude_events(
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
            "speed": e.get("speed"),
            "service_tier": e.get("service_tier"),
            "compaction": False,
        }
        for e in rows
        if e["kind"] == "response"
    ]
    native_requests: dict[str | None, list[dict[str, Any]]] = {}
    for event in rows:
        if event["kind"] == "response":
            native_requests.setdefault(event.get("request_id"), []).append(event)
    unidentified = native_requests.pop(None, None) is not None
    # One API request yields one message, so a reused request id means a doctored transcript.
    if any(len(responses) > 1 for responses in native_requests.values()):
        reasons.append("native_request_identity_reused")
    compactions = [e for e in rows if e["kind"] == "compaction"]
    tools = {e["call_id"] for e in rows if e["kind"] == "tool_call"}
    versions = {e.get("native_version") for e in sessions}
    otel = [e for e in rows if e["source"] == "otel"]
    otel_requests, otel_compactions, native_cost = set(), 0, Decimal(0)
    for event in otel:
        attrs = event["attributes"]
        if attrs.get("app.version"):
            versions.add(attrs["app.version"])
        call = attrs.get("tool_use_id")
        if event["kind"] == "claude_code.tool_result" and call and call not in tools:
            tools.add(call)
            reasons.append("otel_tool_call_without_transcript")
        if event["kind"] != "claude_code.api_request":
            continue
        try:
            # Absent when its value had no real shape; Claude Code always reports one.
            cost = attrs.get("cost_usd")
            if not isinstance(cost, str):
                raise InvalidOperation
            cost = Decimal(cost)
            # A client-side per-request estimate; no real request approaches a million dollars.
            if not cost.is_finite() or not 0 <= cost < MAX_REQUEST_COST_USD:
                raise InvalidOperation
            native_cost += cost
        except InvalidOperation:
            reasons.append("otel_cost_malformed")
        request = attrs.get("request_id")
        otel_requests.add(request)
        if request in native_requests:
            for native in native_requests[request]:
                _reconcile(native, attrs, reasons)
            continue
        compaction = attrs.get("query_source") == "compact"
        otel_compactions += compaction
        if not compaction:
            reasons.append("native_usage_unavailable_for_request")
        requests.append(
            {
                "response_id": event["id"],
                "thread_id": event.get("thread_id"),
                "model": attrs.get("model"),
                "usage": _otel_usage(attrs),
                "timestamp_ms": event["timestamp_ms"],
                "speed": _OTEL_SPEEDS.get(attrs.get("speed"), attrs.get("speed")),
                "compaction": compaction,
                "response_identity": "otel_observation",
            }
        )
    if otel and native_requests.keys() - otel_requests:
        reasons.append("otel_missing_native_request")
    if otel and unidentified:
        # A response without its request id cannot be matched to anything OTel reported.
        reasons.append("otel_usage_comparison_unavailable")
    unresolved = max(0, len(compactions) - otel_compactions)
    if otel_compactions > len(compactions):
        reasons.append("otel_compaction_without_boundary")
    if unresolved:
        reasons.append("compaction_usage_unavailable")
    if not sessions:
        reasons.append("native_journals_unavailable")
    if not versions - {None} or not versions - {None} <= QUALIFIED_CLAUDE_VERSIONS:
        reasons.append("native_version_not_qualified")
    opened = {e["turn_id"] for e in rows if e["kind"] == "task_started"}
    closed = {e["turn_id"] for e in rows if e["kind"] == "task_complete"}
    if opened - closed:
        reasons.append("native_turn_not_completed")
    if exit_kind != "completed":
        reasons.append("execution_did_not_complete")
    present = bool(sessions or otel)
    if present and not opened:
        reasons.append("native_turn_start_unobserved")
    return _measurements(
        requests,
        len(requests) + unresolved,
        len(tools),
        reasons,
        present,
        {
            "native_versions": sorted(v for v in versions if v),
            "native_threads": len(sessions),
            "observed_threads": len(
                {e["thread_id"] for e in sessions}
                | {e.get("thread_id") for e in otel if e.get("thread_id")}
            ),
            "remote_or_local_compactions": len(compactions),
            "deduplicated_events": len(rows),
            "exit_kind": exit_kind,
            "model_basis": "native_message_model; observation, not provider attestation",
            # Claude Code's own client-side estimate, kept only to cross-check the bench's.
            "native_reported_cost_usd": format(native_cost, "f") if otel else None,
        },
    )


class ClaudeTelemetryCollector(CodexTelemetryCollector):
    """The Codex collector's receiver and sink, fed by Claude Code's transcripts and OTel."""

    adapter = "claude"

    def otel_environment(self, endpoint: str | None = None) -> dict[str, str]:
        """Claude Code reads its exporter only from the environment, never project settings."""
        self.config_toml(endpoint)  # the same endpoint validation
        return {
            "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
            "OTEL_LOGS_EXPORTER": "otlp",
            "OTEL_METRICS_EXPORTER": "none",
            "OTEL_TRACES_EXPORTER": "none",
            "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/json",
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": endpoint or self.endpoint,
            "OTEL_LOGS_EXPORT_INTERVAL": "1000",
            "OTEL_METRICS_INCLUDE_VERSION": "true",
            # Pinned off over any construct value: no prompts, responses, tool arguments or
            # content, raw API bodies, managed settings, or beta tracing reach the relay.
            "OTEL_LOG_USER_PROMPTS": "0",
            "OTEL_LOG_ASSISTANT_RESPONSES": "0",
            "OTEL_LOG_TOOL_DETAILS": "0",
            "OTEL_LOG_TOOL_CONTENT": "0",
            "OTEL_LOG_RAW_API_BODIES": "0",
            "OTEL_LOG_MANAGED_SETTINGS": "0",
            "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "0",
        }

    def ingest_otlp(self, payload: dict[str, Any]) -> None:
        problems: list[str] = []
        for event in normalize_claude_otlp(payload, problems):
            self._append(event)
        if problems:
            self.mark_incomplete("otel_label_rejected")

    def harvest_native(self, native_state: Path, *, max_bytes: int = MAX_TRANSCRIPT_BYTES) -> None:
        """Read project transcripts only, never credentials, through descriptors without links."""
        try:
            projects = open_directory(Path(native_state), ("projects",))
        except OSError:
            self.mark_incomplete("native_sessions_unavailable")
            return
        files = 0
        try:
            for _, content in iter_regular_files(
                projects,
                accept=lambda path: PurePosixPath(path).suffix == ".jsonl",
                max_files=MAX_TRANSCRIPT_FILES,
                max_bytes=max_bytes,
            ):
                try:
                    # Only "\n" ends a record: JSON.stringify leaves U+2028 and U+0085 raw.
                    text = io.StringIO(content.decode("utf-8"), newline="\n")
                    rows, problems = normalize_transcript(text)
                except UnicodeError:
                    self.mark_incomplete("native_journal_unreadable")
                    continue
                for row in rows:
                    self._append(row)
                for problem in problems:
                    self.mark_incomplete(problem)
                files += 1
        except TreeLimitExceeded:
            self.mark_incomplete("native_journal_size_limit")
        except OSError:
            self.mark_incomplete("native_journal_unreadable")
        finally:
            os.close(projects)
        if not files:
            self.mark_incomplete("native_journals_unavailable")

    def finalize(self, *, exit_kind: str, native_version: str | None = None) -> dict[str, Any]:
        if native_version is not None and native_version not in QUALIFIED_CLAUDE_VERSIONS:
            self.mark_incomplete("native_version_not_qualified")
        return self._write_summary(summarize_claude_events, exit_kind)
