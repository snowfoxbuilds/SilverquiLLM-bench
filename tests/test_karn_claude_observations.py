"""Claude Code accounting from sanitized transcripts, cross-checked by OTel (synthetic data)."""

from __future__ import annotations

import json
import urllib.request
from decimal import Decimal

import pytest

from silverquillm.karn.claude_observations import (
    QUALIFIED_CLAUDE_VERSIONS,
    ClaudeTelemetryCollector,
    claude_usage,
    normalize_claude_otlp,
    normalize_transcript,
    summarize_claude_events,
)
from silverquillm.karn.host import NATIVE_TELEMETRY_ENVIRONMENT
from silverquillm.karn.observations import summarize_events

SESSION = "0b9c7f6e-1111-4222-8333-944455556666"


def usage(uncached=10, read=4000, written=300, written_1h=100, output=50):
    return {
        "input_tokens": uncached,
        "cache_read_input_tokens": read,
        "cache_creation_input_tokens": written,
        "cache_creation": {
            "ephemeral_5m_input_tokens": written - written_1h,
            "ephemeral_1h_input_tokens": written_1h,
        },
        "output_tokens": output,
        "output_tokens_details": {"thinking_tokens": 7},
        "service_tier": "standard",
        "speed": "standard",
    }


def line(kind, *, sidechain=False, second=0, **fields):
    value = {
        "type": kind,
        "sessionId": SESSION,
        "isSidechain": sidechain,
        "version": "2.1.284",
        "timestamp": f"2026-09-28T00:00:{second:02}.000Z",
        "uuid": f"uuid-{kind}-{second}",
        **fields,
    }
    if sidechain:
        value["agentId"] = "a0123456789abcdef"
    return json.dumps(value)


def assistant(message_id, request, blocks, *, stop=None, second=1, sidechain=False, **usage_args):
    rows = []
    for index, block in enumerate(blocks):
        rows.append(
            line(
                "assistant",
                sidechain=sidechain,
                second=second,
                requestId=request,
                message={
                    "id": message_id,
                    "model": "claude-opus-5-5",
                    "content": [block],
                    "stop_reason": stop if index == len(blocks) - 1 else None,
                    "usage": usage(**usage_args),
                },
            )
        )
    return rows


def prompt(second=0):
    return line("user", second=second, message={"role": "user", "content": "private prompt"})


def tool_use(call):
    return {"type": "tool_use", "id": call, "name": "Bash", "input": {"command": "secret"}}


def main_transcript():
    return [
        prompt(),
        *assistant(
            "msg_01", "req_01", [{"type": "thinking"}, tool_use("toolu_01")], stop="tool_use"
        ),
        line(
            "user",
            second=2,
            message={"content": [{"type": "tool_result", "tool_use_id": "toolu_01"}]},
        ),
        *assistant("msg_02", "req_02", [{"type": "text", "text": "done"}], stop="end_turn"),
    ]


def events_of(*transcripts):
    rows = []
    for transcript in transcripts:
        found, problems = normalize_transcript(transcript)
        assert problems == []
        rows += found
    return rows


def test_usage_is_normalized_to_include_cache_reads_and_writes():
    assert claude_usage(usage()) == {
        "input_tokens": 10 + 4000 + 300,
        "cached_input_tokens": 4000,
        "cache_write_input_tokens": 300,
        "cache_write_1h_input_tokens": 100,
        "output_tokens": 50,
        "reasoning_output_tokens": 7,
        "total_tokens": 4360,
    }
    inconsistent = usage()
    inconsistent["cache_creation"]["ephemeral_1h_input_tokens"] = 999
    assert claude_usage(inconsistent)["cache_write_1h_input_tokens"] is None
    assert claude_usage({"input_tokens": 1})["input_tokens"] is None


def test_a_message_split_across_block_lines_counts_once_with_its_tools():
    result = summarize_claude_events(events_of(main_transcript()), exit_kind="completed")
    assert result["agent_turns"]["responses"]["value"] == 2
    assert result["agent_turns"]["tool_calls"]["value"] == 1
    assert result["usage"]["value"]["input_tokens"] == 2 * 4310
    assert result["cost_breakdown"]["value"]["cache_write_1h"]["tokens"] == 200
    assert sum(Decimal(p["usd"]) for p in result["cost_breakdown"]["value"].values()) == Decimal(
        result["estimated_cost"]["value"]
    )


def test_an_unqualified_version_keeps_values_but_marks_them_partial():
    assert "2.1.284" not in QUALIFIED_CLAUDE_VERSIONS
    result = summarize_claude_events(events_of(main_transcript()), exit_kind="completed")
    assert result["estimated_cost"]["completeness"] == "partial"
    assert result["estimated_cost"]["reasons"] == ["native_version_not_qualified"]


def test_subagent_transcripts_add_their_own_responses_and_tools():
    child = [
        line("user", sidechain=True, message={"content": "task"}),
        *assistant(
            "msg_c1", "req_c1", [tool_use("toolu_c1")], stop="tool_use", sidechain=True, second=3
        ),
    ]
    result = summarize_claude_events(events_of(main_transcript(), child), exit_kind="completed")
    assert result["agent_turns"]["responses"]["value"] == 3
    assert result["agent_turns"]["tool_calls"]["value"] == 2
    assert result["coverage"]["native_threads"] == 2
    assert "native_turn_not_completed" not in result["agent_turns"]["total"]["reasons"]


def test_an_unfinished_main_thread_is_not_a_completed_turn():
    transcript = [prompt(), *assistant("msg_01", "req_01", [tool_use("t")], stop="tool_use")]
    result = summarize_claude_events(events_of(transcript), exit_kind="completed")
    assert "native_turn_not_completed" in result["agent_turns"]["total"]["reasons"]


def test_synthetic_error_messages_are_not_model_responses():
    transcript = main_transcript() + [
        line(
            "assistant",
            second=5,
            message={"id": "msg_x", "model": "<synthetic>", "content": [], "usage": usage()},
        )
    ]
    result = summarize_claude_events(events_of(transcript), exit_kind="completed")
    assert result["agent_turns"]["responses"]["value"] == 2


@pytest.mark.parametrize(
    "hostile",
    [
        "[" * 100000 + "]" * 100000,
        json.dumps({"type": "assistant", "sessionId": SESSION, "message": {"id": "m", "content": 5}}),
        json.dumps(
            {"type": "assistant", "sessionId": SESSION, "message": {"id": "m", "stop_reason": []}}
        ),
        json.dumps({"type": "assistant", "sessionId": SESSION, "message": {"id": "m", "usage": 1}}),
    ],
)
def test_a_hostile_transcript_line_cannot_break_accounting(hostile):
    rows, _ = normalize_transcript([*main_transcript(), hostile])
    result = summarize_claude_events(rows, exit_kind="completed")
    assert result["agent_turns"]["tool_calls"]["value"] == 1


def test_non_finite_otel_costs_are_dropped_or_flagged():
    [event] = normalize_claude_otlp(otlp(request_id="r", cost_usd=float("inf")))
    assert "cost_usd" not in event["attributes"]
    flagged = api_request("req_01", cost_usd="NaN") + api_request("req_02")
    result = summarize_claude_events(events_of(main_transcript()) + flagged, exit_kind="completed")
    assert "otel_cost_malformed" in result["estimated_cost"]["reasons"]


def otlp(name="claude_code.api_request", **attrs):
    values = {
        "event.name": name,
        "event.timestamp": "2026-09-28T00:00:09.000Z",
        "session.id": SESSION,
        "app.version": "2.1.284",
        "model": "claude-opus-5-5",
        "user.email": "person@example.com",
        "organization.id": "org-secret",
        "prompt": "private prompt",
        **attrs,
    }
    attributes = []
    for key, value in values.items():
        if isinstance(value, float):
            attributes.append({"key": key, "value": {"doubleValue": value}})
        else:
            attributes.append({"key": key, "value": {"stringValue": str(value)}})
    return {"resourceLogs": [{"scopeLogs": [{"logRecords": [{"attributes": attributes}]}]}]}


def api_request(request, source="repl_main_thread", **overrides):
    values = {
        "request_id": request,
        "query_source": source,
        "input_tokens": "10",
        "cache_read_tokens": "4000",
        "cache_creation_tokens": "0",
        "output_tokens": "50",
        "cost_usd": 0.0123,
        **overrides,
    }
    return normalize_claude_otlp(otlp(**values))


def test_otel_normalization_keeps_accounting_and_drops_identity_and_content():
    [event] = api_request("req_01")
    assert event["kind"] == "claude_code.api_request"
    assert event["thread_id"] == SESSION
    assert event["attributes"]["cost_usd"] == "0.0123"
    assert not {"user.email", "organization.id", "prompt"} & set(event["attributes"])
    assert normalize_claude_otlp(otlp(name="api_request", request_id="r"))[0]["kind"] == (
        "claude_code.api_request"
    )
    assert normalize_claude_otlp(otlp(name="claude_code.user_prompt")) == []


def test_a_compaction_request_is_priced_from_otel_and_counted_once():
    transcript = main_transcript() + [
        line("system", second=4, subtype="compact_boundary", compactMetadata={"preTokens": 9})
    ]
    native = events_of(transcript)
    without = summarize_claude_events(native, exit_kind="completed")
    assert without["agent_turns"]["responses"]["value"] == 3
    assert "compaction_usage_unavailable" in without["estimated_cost"]["reasons"]
    otel = api_request("req_01") + api_request("req_02") + api_request("req_c", "compact")
    both = summarize_claude_events(native + otel, exit_kind="completed")
    assert both["agent_turns"]["responses"]["value"] == 3
    assert "compaction_usage_unavailable" not in both["estimated_cost"]["reasons"]
    compaction = next(r for r in both["requests"] if r["compaction"])
    assert compaction["usage"]["input_tokens"] == 4010
    assert both["coverage"]["native_reported_cost_usd"] == "0.0369"


def test_otel_cross_check_flags_requests_missing_from_either_stream():
    native = events_of(main_transcript())
    result = summarize_claude_events(native + api_request("req_01"), exit_kind="completed")
    assert "otel_missing_native_request" in result["usage"]["reasons"]
    extra = summarize_claude_events(
        native + api_request("req_01") + api_request("req_02") + api_request("req_99"),
        exit_kind="completed",
    )
    assert "native_usage_unavailable_for_request" in extra["usage"]["reasons"]
    assert extra["agent_turns"]["responses"]["value"] == 3


def test_an_otel_tool_result_joins_the_transcript_call_by_id():
    native = events_of(main_transcript())
    otel = normalize_claude_otlp(
        otlp(name="claude_code.tool_result", tool_use_id="toolu_01", tool_name="Bash")
    )
    otel += normalize_claude_otlp(otlp(name="claude_code.tool_result", tool_use_id="toolu_09"))
    result = summarize_claude_events(native + otel, exit_kind="completed")
    assert result["agent_turns"]["tool_calls"]["value"] == 2


def test_summaries_dispatch_on_the_recorded_adapter():
    native = events_of(main_transcript())
    assert summarize_events(native, exit_kind="completed", adapter="claude") == (
        summarize_claude_events(native, exit_kind="completed")
    )


def test_harvest_reads_transcripts_only_and_never_credentials_or_links(tmp_path):
    work = tmp_path / "work"
    session = work / "projects/-workspace"
    (session / SESSION / "subagents").mkdir(parents=True)
    (session / (SESSION + ".jsonl")).write_text("\n".join(main_transcript()))
    (session / SESSION / "subagents/agent-a.meta.json").write_text("{}")
    (work / ".credentials.json").write_text('{"claudeAiOauth": {"accessToken": "secret"}}')
    outside = tmp_path / "outside.jsonl"
    outside.write_text("\n".join(main_transcript()))
    (session / "linked.jsonl").symlink_to(outside)
    with ClaudeTelemetryCollector(tmp_path / "run") as collector:
        collector.harvest_native(work)
        result = collector.finalize(exit_kind="completed")
    assert result["agent_turns"]["responses"]["value"] == 2
    retained = (tmp_path / "run/observations.events.jsonl").read_text()
    assert "secret" not in retained and "private prompt" not in retained


def test_a_missing_projects_tree_is_explicit(tmp_path):
    with ClaudeTelemetryCollector(tmp_path / "run") as collector:
        collector.harvest_native(tmp_path / "work")
        result = collector.finalize(exit_kind="completed")
    assert result["usage"]["value"] is None
    assert "native_sessions_unavailable" in result["usage"]["reasons"]


def test_the_receiver_ingests_claude_code_otlp_json(tmp_path):
    with ClaudeTelemetryCollector(tmp_path / "run") as collector:
        body = json.dumps(otlp(request_id="req_01", input_tokens="1")).encode()
        request = urllib.request.Request(
            collector.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
        assert [e["kind"] for e in collector.events] == ["claude_code.api_request"]


def qualification():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "scripts/qualify_claude_telemetry.py"
    spec = importlib.util.spec_from_file_location("qualify_claude_telemetry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.qualify


def raw_events(*groups):
    return "\n".join(json.dumps(e, sort_keys=True) for group in groups for e in group).encode()


def test_a_run_whose_streams_agree_qualifies_its_version():
    tool = normalize_claude_otlp(otlp(name="claude_code.tool_result", tool_use_id="toolu_01"))
    otel = api_request("req_01", cache_creation_tokens="300", input_tokens="10")
    otel += api_request("req_02", cache_creation_tokens="300", input_tokens="10")
    proof = qualification()(raw_events(events_of(main_transcript()), otel, tool))
    assert proof["mismatches"] == []
    assert proof["qualified"] is True
    assert proof["native_binary"] == "claude-code 2.1.284"


def test_disagreeing_token_counts_do_not_qualify():
    otel = api_request("req_01") + api_request("req_02")
    proof = qualification()(raw_events(events_of(main_transcript()), otel))
    assert proof["qualified"] is False
    assert {m["check"] for m in proof["mismatches"]} >= {"usage_agrees", "tool_calls_agree"}


def test_every_qualified_claude_version_replays_its_committed_proof():
    import hashlib
    from pathlib import Path

    for version in QUALIFIED_CLAUDE_VERSIONS:
        fixture = Path(__file__).parent / "fixtures" / ("karn_observations_claude_" + version)
        proof = json.loads((fixture / "qualification.json").read_text())
        raw = (fixture / "events.jsonl").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == proof["events_sha256"]
        assert qualification()(raw) == proof


def test_the_exporter_environment_is_allowlisted_and_never_logs_prompts(tmp_path):
    with ClaudeTelemetryCollector(tmp_path / "run") as collector:
        environment = collector.otel_environment("http://10.0.0.2:3128/v1/logs")
        with pytest.raises(ValueError):
            collector.otel_environment("file:///etc/passwd")
    assert set(environment) <= NATIVE_TELEMETRY_ENVIRONMENT
    assert environment["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"] == "http://10.0.0.2:3128/v1/logs"
    assert environment["OTEL_LOG_USER_PROMPTS"] == "0"
    assert environment["OTEL_EXPORTER_OTLP_LOGS_PROTOCOL"] == "http/json"
