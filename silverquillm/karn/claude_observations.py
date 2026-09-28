"""Sanitized native Claude Code observations: session transcripts plus an OTel cross-check.

The transcript under the config directory is the durable source, harvested after container
stop and before the login plugin clears its work directory; recovery reads the same copy.
Claude Code writes one transcript line per content block of an assistant message, each
repeating the message's usage, so accounting is keyed by message id. A compaction's own
request never appears in the transcript; its OTel ``api_request`` supplies the usage.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any

from silverquillm.safe_files import TreeLimitExceeded, iter_regular_files, open_directory

from .observations import (
    CodexTelemetryCollector,
    _fingerprint,
    _integer,
    _label,
    _measurements,
    _stamp,
)

# Versions whose transcript and OTel streams were checked against each other on a real run.
QUALIFIED_CLAUDE_VERSIONS: frozenset[str] = frozenset()
MAX_TRANSCRIPT_BYTES = 128 * 1024 * 1024
MAX_TRANSCRIPT_FILES = 10_000
_EVENTS = {"claude_code.api_request", "claude_code.tool_result", "claude_code.api_error"}
# Identity attributes (user.email, user.account_uuid, organization.id, ...), prompts and tool
# arguments are never retained.
_ATTRIBUTES = {
    "event.name",
    "event.timestamp",
    "event.sequence",
    "session.id",
    "app.version",
    "model",
    "request_id",
    "query_source",
    "agent.name",
    "speed",
    "effort",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "cost_usd",
    "duration_ms",
    "tool_name",
    "tool_use_id",
    "success",
    "status_code",
    "attempt",
}
_FINISHED = {"end_turn", "stop_sequence"}


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
            thread = _label(record.get("agentId") if sidechain else record.get("sessionId"))
        version = version or _label(record.get("version"))
        if kind == "user" and not sidechain and not record.get("isMeta"):
            started = True
        elif kind == "system" and record.get("subtype") == "compact_boundary":
            boundary = _label(record.get("uuid"))
            if boundary:
                events.append(base("compaction", "compaction:" + boundary, timestamp))
            else:
                problems.append("compaction_identity_missing")
        elif kind == "assistant":
            message = record.get("message")
            if not isinstance(message, dict) or message.get("model") == "<synthetic>":
                continue
            response = _label(message.get("id"))
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
                request_id=_label(record.get("requestId")),
                owner_thread_id=thread,
                model=_label(message.get("model")),
                usage=claude_usage(usage),
                speed=_label(usage.get("speed")),
                service_tier=_label(usage.get("service_tier")),
            )
            if not sidechain:
                last_stop = _label(message.get("stop_reason"))
            content = message.get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    call = _label(block.get("id"))
                    if call:
                        tools[call] = base(
                            "tool_call",
                            "tool:" + call,
                            timestamp,
                            call_id=call,
                            tool_name=_label(block.get("name")) or "tool_use",
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


def normalize_claude_otlp(payload: Any) -> list[dict[str, Any]]:
    """Keep allowlisted Claude Code accounting events; drop identities, prompts and arguments."""
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
                    if isinstance(value, bool) or _label(value) is not None:
                        attrs[key] = value
                    elif type(value) is int:
                        attrs[key] = str(value)
                name = attrs.get("event.name")
                if name is None:
                    body = record.get("body", {})
                    name = _label(body.get("stringValue")) if isinstance(body, dict) else None
                # The event is named with or without its claude_code prefix.
                if isinstance(name, str) and not name.startswith("claude_code."):
                    name = "claude_code." + name
                attrs["event.name"] = name
                if name not in _EVENTS:
                    continue
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
    native_requests = {e.get("request_id") for e in rows if e["kind"] == "response"} - {None}
    compactions = [e for e in rows if e["kind"] == "compaction"]
    tools = {e["call_id"] for e in rows if e["kind"] == "tool_call"}
    versions = {e.get("native_version") for e in sessions}
    otel = [e for e in rows if e["source"] == "otel"]
    otel_requests, otel_compactions, native_cost = set(), 0, Decimal(0)
    for event in otel:
        attrs = event["attributes"]
        if attrs.get("app.version"):
            versions.add(attrs["app.version"])
        if event["kind"] == "claude_code.tool_result" and attrs.get("tool_use_id"):
            tools.add(attrs["tool_use_id"])
        if event["kind"] != "claude_code.api_request":
            continue
        try:
            cost = Decimal(attrs.get("cost_usd", "0"))
            if not cost.is_finite() or cost < 0:
                raise InvalidOperation
            native_cost += cost
        except InvalidOperation:
            reasons.append("otel_cost_malformed")
        request = attrs.get("request_id")
        otel_requests.add(request)
        if request in native_requests:
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
                "speed": attrs.get("speed"),
                "compaction": compaction,
                "response_identity": "otel_observation",
            }
        )
    if otel and native_requests - otel_requests:
        reasons.append("otel_missing_native_request")
    unresolved = max(0, len(compactions) - otel_compactions)
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
            "OTEL_LOG_USER_PROMPTS": "0",
            "OTEL_LOG_TOOL_DETAILS": "0",
        }

    def ingest_otlp(self, payload: dict[str, Any]) -> None:
        for event in normalize_claude_otlp(payload):
            self._append(event)

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
                    rows, problems = normalize_transcript(content.decode("utf-8").splitlines())
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
