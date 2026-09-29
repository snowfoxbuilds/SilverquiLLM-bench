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


# Synthetic transcripts use a version never qualified, so they stay partial.
SYNTHETIC_VERSION = "2.1.999"


def line(kind, *, sidechain=False, second=0, **fields):
    value = {
        "type": kind,
        "sessionId": SESSION,
        "isSidechain": sidechain,
        "version": SYNTHETIC_VERSION,
        "timestamp": f"2026-09-28T00:00:{second:02}.000Z",
        "uuid": f"00000000-0000-4000-8000-{second:012d}",
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
    assert SYNTHETIC_VERSION not in QUALIFIED_CLAUDE_VERSIONS
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
    transcript = [prompt(), *assistant("msg_01", "req_01", [tool_use("toolu_t")], stop="tool_use")]
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
        json.dumps(
            {"type": "assistant", "sessionId": SESSION, "message": {"id": "m", "content": 5}}
        ),
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
    [event] = normalize_claude_otlp(otlp(request_id="req_r", cost_usd=float("inf")))
    assert "cost_usd" not in event["attributes"]
    flagged = api_request("req_01", cost_usd="NaN") + api_request("req_02")
    result = summarize_claude_events(events_of(main_transcript()) + flagged, exit_kind="completed")
    assert "otel_cost_malformed" in result["estimated_cost"]["reasons"]


@pytest.mark.parametrize("cost", ["1E+1000000", "9E+999999"])
def test_an_absurd_otel_cost_is_flagged_not_raised_or_expanded(cost):
    otel = api_request("req_01", cost_usd=cost) + api_request("req_02")
    result = summarize_claude_events(events_of(main_transcript()) + otel, exit_kind="completed")
    assert "otel_cost_malformed" in result["estimated_cost"]["reasons"]
    assert result["coverage"]["native_reported_cost_usd"] == "0.0123"


def test_a_boolean_otel_cost_is_not_read_as_one_dollar():
    [event] = normalize_claude_otlp(
        {
            "resourceLogs": [
                {
                    "scopeLogs": [
                        {
                            "logRecords": [
                                {
                                    "attributes": [
                                        {
                                            "key": "event.name",
                                            "value": {"stringValue": "api_request"},
                                        },
                                        {"key": "request_id", "value": {"stringValue": "req_01"}},
                                        {"key": "cost_usd", "value": {"boolValue": True}},
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    )
    result = summarize_claude_events(
        events_of(main_transcript()) + [event] + api_request("req_02"), exit_kind="completed"
    )
    assert "otel_cost_malformed" in result["estimated_cost"]["reasons"]
    assert result["coverage"]["native_reported_cost_usd"] == "0.0123"


def test_unescaped_unicode_line_separators_in_content_do_not_split_records(tmp_path):
    # JSON.stringify leaves U+2028, U+2029 and U+0085 raw; only "\n" ends a transcript line.
    text = {"type": "text", "text": "a b c\x85d"}
    transcript = [prompt(), *assistant("msg_01", "req_01", [text], stop="end_turn")]
    session = tmp_path / "work/projects/-workspace"
    session.mkdir(parents=True)
    (session / (SESSION + ".jsonl")).write_text(
        "\n".join(json.dumps(json.loads(row), ensure_ascii=False) for row in transcript) + "\n"
    )
    with ClaudeTelemetryCollector(tmp_path / "run") as collector:
        collector.harvest_native(tmp_path / "work")
        result = collector.finalize(exit_kind="completed")
    assert result["agent_turns"]["responses"]["value"] == 1
    assert "native_record_malformed" not in result["usage"]["reasons"]


def test_a_pathologically_deep_projects_tree_marks_the_harvest_incomplete(tmp_path):
    from .test_karn_claude_login import nest

    work = tmp_path / "work"
    session = work / "projects/-workspace"
    session.mkdir(parents=True)
    (session / (SESSION + ".jsonl")).write_text("\n".join(main_transcript()))
    nest(session, 1200)
    with ClaudeTelemetryCollector(tmp_path / "run") as collector:
        collector.harvest_native(work)
        result = collector.finalize(exit_kind="completed")
    assert "native_journal_size_limit" in result["usage"]["reasons"]


def otlp(name="claude_code.api_request", **attrs):
    values = {
        "event.name": name,
        "event.timestamp": "2026-09-28T00:00:09.000Z",
        "session.id": SESSION,
        "app.version": SYNTHETIC_VERSION,
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
        "cache_creation_tokens": "300",
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
    assert normalize_claude_otlp(otlp(name="api_request", request_id="req_r"))[0]["kind"] == (
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
    otel = (
        api_request("req_01")
        + api_request("req_02")
        + api_request("req_c", "compact", cache_creation_tokens="0")
    )
    both = summarize_claude_events(native + otel, exit_kind="completed")
    assert both["agent_turns"]["responses"]["value"] == 3
    assert "compaction_usage_unavailable" not in both["estimated_cost"]["reasons"]
    compaction = next(r for r in both["requests"] if r["compaction"])
    assert compaction["usage"]["input_tokens"] == 4010
    assert both["coverage"]["native_reported_cost_usd"] == "0.0369"


def test_a_compaction_at_otel_normal_speed_is_priced_as_standard():
    # Claude Code's OTel names the API's "standard" speed "normal".
    transcript = main_transcript() + [line("system", second=4, subtype="compact_boundary")]
    otel = api_request("req_01") + api_request("req_02")
    otel += api_request("req_c", "compact", cache_creation_tokens="0", speed="normal")
    result = summarize_claude_events(events_of(transcript) + otel, exit_kind="completed")
    compaction = next(
        row for row in result["request_prices"] if row["response_id"].startswith("otel:")
    )
    assert compaction["usd"] is not None, compaction["reasons"]
    fast = summarize_claude_events(
        events_of(transcript)
        + otel[:2]
        + api_request("req_c", "compact", cache_creation_tokens="0", speed="fast"),
        exit_kind="completed",
    )
    assert "nonstandard_processing_unpriced" in fast["estimated_cost"]["reasons"]


def test_an_otel_compaction_without_a_transcript_boundary_is_flagged():
    native = events_of(main_transcript())
    otel = api_request("req_01") + api_request("req_02")
    otel += api_request("req_c", "compact", input_tokens="999999", output_tokens="999999")
    result = summarize_claude_events(native + otel, exit_kind="completed")
    assert "otel_compaction_without_boundary" in result["usage"]["reasons"]


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


QUALIFIED = min(QUALIFIED_CLAUDE_VERSIONS)


def qualified(events):
    """The synthetic streams relabelled as a qualified version, so agreement is complete."""
    events = json.loads(json.dumps(events))
    for event in events:
        if event["kind"] == "session":
            event["native_version"] = QUALIFIED
        if event["source"] == "otel":
            event["attributes"]["app.version"] = QUALIFIED
    return events


def reconciled(*otel):
    return summarize_claude_events(
        qualified(events_of(main_transcript()) + [e for group in otel for e in group]),
        exit_kind="completed",
    )


def test_agreeing_streams_on_a_qualified_version_are_complete():
    agreed = reconciled(api_request("req_01"), api_request("req_02"))
    native_only = summarize_claude_events(
        qualified(events_of(main_transcript())), exit_kind="completed"
    )
    for key in ("usage", "estimated_cost", "cost_breakdown"):
        assert agreed[key]["completeness"] == "complete", agreed[key]["reasons"]
        assert agreed[key]["value"] == native_only[key]["value"]


@pytest.mark.parametrize(
    "field",
    ["input_tokens", "cache_read_tokens", "cache_creation_tokens", "output_tokens"],
)
def test_a_token_field_otel_disagrees_on_keeps_native_values_but_is_partial(field):
    expected = reconciled(api_request("req_01"), api_request("req_02"))
    result = reconciled(api_request("req_01", **{field: "7"}), api_request("req_02"))
    for key in ("usage", "estimated_cost", "cost_breakdown"):
        assert result[key]["value"] == expected[key]["value"]
        assert result[key]["completeness"] == "partial"
        assert "otel_usage_conflicts_with_native" in result[key]["reasons"]
    assert result["requests"] == expected["requests"]


def test_a_model_otel_disagrees_on_is_flagged():
    result = reconciled(api_request("req_01", model="claude-haiku-4-5"), api_request("req_02"))
    assert "otel_model_conflicts_with_native" in result["usage"]["reasons"]
    assert {r["model"] for r in result["requests"]} == {"claude-opus-5-5"}


@pytest.mark.parametrize(
    "field",
    ["input_tokens", "cache_read_tokens", "cache_creation_tokens", "output_tokens", "model"],
)
def test_a_field_missing_from_otel_leaves_the_comparison_unavailable(field):
    [event] = api_request("req_01")
    del event["attributes"][field]
    result = reconciled([event], api_request("req_02"))
    assert result["usage"]["completeness"] == "partial"
    reason = (
        "otel_model_comparison_unavailable"
        if field == "model"
        else ("otel_usage_comparison_unavailable")
    )
    assert reason in result["usage"]["reasons"]


def test_a_transcript_response_without_a_request_id_cannot_be_reconciled():
    transcript = [
        row.replace('"requestId": "req_02", ', "") if '"req_02"' in row else row
        for row in main_transcript()
    ]
    events = qualified(events_of(transcript) + api_request("req_01") + api_request("req_02"))
    result = summarize_claude_events(events, exit_kind="completed")
    assert "otel_usage_comparison_unavailable" in result["usage"]["reasons"]


@pytest.mark.parametrize("first", [True, False])
def test_a_request_id_reused_by_a_second_response_is_flagged(first):
    extra = assistant("msg_00", "req_01", [{"type": "text"}], uncached=99999, output=77777)
    body = main_transcript()
    transcript = [body[0], *extra, *body[1:]] if first else [*body, *extra]
    events = qualified(events_of(transcript) + api_request("req_01") + api_request("req_02"))
    result = summarize_claude_events(events, exit_kind="completed")
    assert result["usage"]["completeness"] == "partial"
    assert "native_request_identity_reused" in result["usage"]["reasons"]
    assert "otel_usage_conflicts_with_native" in result["usage"]["reasons"]


def test_a_malformed_retained_response_degrades_instead_of_crashing():
    events = qualified(events_of(main_transcript()) + api_request("req_01") + api_request("req_02"))
    for event in events:
        if event["kind"] == "response":
            del event["usage"]["output_tokens"]
    result = summarize_events(events, exit_kind="interrupted", adapter="claude")
    assert "otel_usage_comparison_unavailable" in result["usage"]["reasons"]


def test_duplicate_observations_reconcile_once_each():
    otel = api_request("req_01") + api_request("req_02")
    repeated = [dict(e, id=e["id"] + "-again") for e in api_request("req_01")]
    native = events_of(main_transcript())
    result = summarize_claude_events(
        qualified(native + native + otel + otel + repeated), exit_kind="completed"
    )
    assert result["usage"]["completeness"] == "complete", result["usage"]["reasons"]
    assert result["agent_turns"]["responses"]["value"] == 2
    conflicting = [dict(e, id=e["id"] + "-again") for e in api_request("req_01", output_tokens="1")]
    flagged = summarize_claude_events(qualified(native + otel + conflicting), exit_kind="completed")
    assert "otel_usage_conflicts_with_native" in flagged["usage"]["reasons"]
    assert flagged["usage"]["value"] == result["usage"]["value"]


def test_recovery_summaries_reconcile_the_same_way():
    events = qualified(
        events_of(main_transcript())
        + api_request("req_01", output_tokens="1")
        + api_request("req_02")
    )
    recovered = summarize_events(events, exit_kind="interrupted", adapter="claude")
    assert "otel_usage_conflicts_with_native" in recovered["usage"]["reasons"]
    assert recovered == summarize_claude_events(events, exit_kind="interrupted")


def test_an_otel_tool_result_joins_the_transcript_call_by_id():
    native = events_of(main_transcript())
    otel = normalize_claude_otlp(
        otlp(name="claude_code.tool_result", tool_use_id="toolu_01", tool_name="Bash")
    )
    joined = summarize_claude_events(native + otel, exit_kind="completed")
    assert joined["agent_turns"]["tool_calls"]["value"] == 1
    assert "otel_tool_call_without_transcript" not in joined["agent_turns"]["total"]["reasons"]
    otel += normalize_claude_otlp(otlp(name="claude_code.tool_result", tool_use_id="toolu_09"))
    result = summarize_claude_events(native + otel, exit_kind="completed")
    # A call only OTel saw still counts, and the gap in the transcript is visible.
    assert result["agent_turns"]["tool_calls"]["value"] == 2
    assert "otel_tool_call_without_transcript" in result["agent_turns"]["total"]["reasons"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sessionId", "sk-ant-oat01-secret"),
        ("requestId", "req_abc def"),
        ("model", "claude-opus-5-5 sk-ant-secret"),
        ("version", "2.1.284-sk-ant"),
    ],
)
def test_a_transcript_label_without_its_real_shape_is_dropped_and_flagged(field, value):
    lines = main_transcript()
    # The session and version come from the first record; request and model from a response.
    index = 0 if field in ("sessionId", "version") else 1
    record = json.loads(lines[index])
    if field == "model":
        record["message"]["model"] = value
    else:
        record[field] = value
    lines[index] = json.dumps(record)
    rows, problems = normalize_transcript(lines)
    assert "native_label_rejected" in problems
    assert value not in json.dumps(rows)


def test_a_tool_label_without_its_real_shape_is_dropped_and_flagged():
    block = {"type": "tool_use", "id": "toolu_ok", "name": "sk-ant-oat01 secret"}
    transcript = [prompt(), *assistant("msg_01", "req_01", [block], stop="end_turn")]
    rows, problems = normalize_transcript(transcript)
    assert "native_label_rejected" in problems
    assert next(r for r in rows if r["kind"] == "tool_call")["tool_name"] == "tool_use"
    bad_id = {"type": "tool_use", "id": "sk-ant-oat01-secret", "name": "Bash"}
    rows, problems = normalize_transcript(
        [prompt(), *assistant("msg_01", "req_01", [bad_id], stop="end_turn")]
    )
    assert "sk-ant" not in json.dumps(rows)
    assert "native_tool_identity_missing" in problems


def test_otel_labels_without_their_real_shape_are_dropped_and_flagged(tmp_path):
    payload = otlp(
        request_id="req_ok",
        tool_name="sk-ant-oat01-secret",
        query_source="agent:sk-ant-secret",
        speed="warp",
    )
    problems = []
    [event] = normalize_claude_otlp(payload, problems)
    assert "tool_name" not in event["attributes"]
    assert "speed" not in event["attributes"]
    assert event["attributes"]["query_source"] == "other"
    assert problems
    with ClaudeTelemetryCollector(tmp_path / "run") as collector:
        collector.ingest_otlp(payload)
        assert "otel_label_rejected" in collector.reasons
    assert "sk-ant" not in (tmp_path / "run/observations.events.jsonl").read_text()


def test_an_api_request_without_a_shaped_cost_is_flagged():
    otel = api_request("req_01", cost_usd="12 dollars") + api_request("req_02")
    result = summarize_claude_events(events_of(main_transcript()) + otel, exit_kind="completed")
    assert "otel_cost_malformed" in result["estimated_cost"]["reasons"]


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
    assert proof["native_binary"] == "claude-code " + SYNTHETIC_VERSION


def test_disagreeing_token_counts_do_not_qualify():
    otel = api_request("req_01", cache_creation_tokens="0") + api_request("req_02")
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
    for gate in (
        "OTEL_LOG_USER_PROMPTS",
        "OTEL_LOG_ASSISTANT_RESPONSES",
        "OTEL_LOG_TOOL_DETAILS",
        "OTEL_LOG_TOOL_CONTENT",
        "OTEL_LOG_RAW_API_BODIES",
        "OTEL_LOG_MANAGED_SETTINGS",
        "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA",
    ):
        assert environment[gate] == "0"
    assert environment["OTEL_EXPORTER_OTLP_LOGS_PROTOCOL"] == "http/json"
