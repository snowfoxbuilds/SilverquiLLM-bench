"""Observation accounting uses request records, never repeated native totals."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal

import pytest

from silverquillm.karn.observations import (
    QUALIFIED_CODEX_VERSIONS,
    CodexTelemetryCollector,
    normalize_otlp,
    normalize_rollout,
    summarize_events,
)
from silverquillm.karn.pricing import price_requests, price_table_metadata


def record(kind, payload, millis=0):
    return json.dumps(
        {"type": kind, "timestamp": f"2026-09-26T00:00:00.{millis:03}Z", "payload": payload}
    )


def usage(input_tokens=100, cached=20, output=30, written=0):
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "cache_write_input_tokens": written,
        "output_tokens": output,
        "reasoning_output_tokens": 5,
        "total_tokens": input_tokens + output,
    }


def journal(*, thread="thread-1", response="response-1", model="gpt-5.4", closed=True):
    lines = [
        record("session_meta", {"id": thread, "cli_version": "0.153.4"}),
        record("event_msg", {"type": "task_started", "turn_id": "turn-1"}),
        record("turn_context", {"model": model}),
    ]
    if response:
        lines.append(
            record(
                "token_usage_record",
                {
                    "response_id": response,
                    "thread_id": thread,
                    "usage": usage(),
                    "thread_token_usage": usage(10000),
                    "turn_token_usage": usage(10000),
                },
                5,
            )
        )
    if closed:
        lines.append(record("event_msg", {"type": "task_complete", "turn_id": "turn-1"}, 10))
    return lines


def otlp(*, name="codex.sse_event", kind="response.created", nanos=1, **attrs):
    values = {
        "event.name": name,
        "event.kind": kind,
        "event.timestamp": "2026-09-26T00:00:00.001Z",
        "conversation.id": "thread-1",
        "app.version": "0.153.4",
        "model": "gpt-5.4",
        **attrs,
    }
    return {
        "resourceLogs": [
            {
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "observedTimeUnixNano": str(nanos),
                                "attributes": [
                                    {"key": key, "value": {"stringValue": str(value)}}
                                    for key, value in values.items()
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }


def test_per_response_usage_deduplicates_embedded_compaction_and_ignores_parent_totals():
    lines = journal()
    response = {
        "response_id": "compact-1",
        "thread_id": "thread-1",
        "usage": usage(200),
        "thread_token_usage": usage(9000),
        "turn_token_usage": usage(9000),
    }
    lines += [
        record("token_usage_record", response),
        record(
            "compacted",
            {
                "compaction_response_id": "compact-1",
                "latest_token_usage_record": response,
                "replacement_history": [{"type": "function_call", "call_id": "historical-call"}],
            },
        ),
    ]
    events, reasons = normalize_rollout(lines)
    result = summarize_events(events, exit_kind="completed", collection_reasons=reasons)
    assert result["agent_turns"]["responses"]["value"] == 2
    assert result["agent_turns"]["tool_calls"]["value"] == 0
    assert result["usage"]["value"]["input_tokens"] == 300
    assert result["coverage"]["remote_or_local_compactions"] == 1


def test_model_request_response_is_not_each_output_item_or_native_user_turn():
    lines = journal()
    lines += [
        record(
            "response_item",
            {
                "type": "message",
                "role": "assistant",
                "id": name,
                "content": [{"text": "not persisted"}],
            },
        )
        for name in ("commentary", "final")
    ]
    events, _ = normalize_rollout(lines)
    assert summarize_events(events, exit_kind="completed")["agent_turns"]["responses"]["value"] == 1


def test_tool_call_count_unions_start_result_and_native_call_including_failed_calls():
    lines = journal() + [
        record(
            "response_item",
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "exec_command",
                "arguments": "secret",
            },
        )
    ]
    events, _ = normalize_rollout(lines)
    events += normalize_otlp(
        otlp(name="codex.tool_decision", call_id="call-1", tool_name="exec_command")
    )
    events += normalize_otlp(
        otlp(name="codex.tool_result", nanos=2, call_id="call-1", success="false")
    )
    result = summarize_events(events, exit_kind="completed")
    assert result["agent_turns"]["tool_calls"]["value"] == 1
    assert result["agent_turns"]["total"]["value"] == 2


def test_descendant_usage_is_added_once_without_summing_ancestor_rollups():
    root, _ = normalize_rollout(journal())
    child, _ = normalize_rollout(journal(thread="child-1", response="child-response"))
    result = summarize_events(root + child + child, exit_kind="completed")
    assert result["agent_turns"]["responses"]["value"] == 2
    assert result["usage"]["value"]["input_tokens"] == 200
    assert result["coverage"]["native_threads"] == 2


def test_missing_observations_are_not_zero_but_confirmed_no_requests_are_zero():
    missing = summarize_events([], exit_kind="failed")
    assert missing["agent_turns"]["total"]["value"] is None
    assert missing["estimated_cost"]["value"] is None
    events, _ = normalize_rollout(journal(response=None))
    zero = summarize_events(events, exit_kind="completed")
    assert zero["agent_turns"]["total"] == {"value": 0, "completeness": "complete", "reasons": []}
    assert zero["estimated_cost"]["value"] == "0"


def test_interrupted_model_response_retains_lower_bound_and_missing_usage():
    events, _ = normalize_rollout(journal(response=None, closed=False))
    events += normalize_otlp(otlp())
    result = summarize_events(events, exit_kind="interrupted")
    assert result["agent_turns"]["responses"]["value"] == 1
    assert result["agent_turns"]["total"]["completeness"] == "partial"
    assert result["usage"]["value"] is None
    assert result["estimated_cost"]["value"] is None


def test_unknown_model_does_not_discard_tokens_or_invent_price():
    events, _ = normalize_rollout(journal(model="future-model"))
    result = summarize_events(events, exit_kind="completed")
    assert result["usage"]["value"]["input_tokens"] == 100
    assert result["estimated_cost"]["value"] is None
    assert "model_price_unavailable" in result["estimated_cost"]["reasons"]


def test_conflicting_response_observation_is_explicit():
    events, _ = normalize_rollout(journal())
    bad = next(e.copy() for e in events if e["kind"] == "response")
    bad["usage"] = usage(101)
    result = summarize_events(events + [bad], exit_kind="completed")
    assert result["usage"]["completeness"] == "partial"
    assert "conflicting_response_observations" in result["usage"]["reasons"]


def test_sanitization_never_retains_native_content_or_otel_arguments_and_credentials():
    payload = otlp(
        name="codex.tool_result",
        call_id="call-1",
        arguments="DO_NOT_RETAIN",
        output="DO_NOT_RETAIN",
        prompt="DO_NOT_RETAIN",
        **{"user.email": "DO_NOT_RETAIN", "auth.header_value": "DO_NOT_RETAIN"},
    )
    sanitized = normalize_otlp(payload)
    lines = journal() + [
        record(
            "response_item",
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "tool",
                "arguments": "DO_NOT_RETAIN",
            },
        )
    ]
    native, _ = normalize_rollout(lines)
    assert "DO_NOT_RETAIN" not in json.dumps(sanitized + native)


def test_receiver_export_retry_is_deduplicated_and_native_capture_never_reads_auth(tmp_path):
    native = tmp_path / "native"
    sessions = native / "sessions" / "nested"
    sessions.mkdir(parents=True)
    (native / "auth.json").write_text("DO_NOT_RETAIN")
    (sessions / "rollout-one.jsonl").write_text("\n".join(journal()))
    (sessions / "rollout-unsafe.jsonl").symlink_to(native / "auth.json")
    with CodexTelemetryCollector(tmp_path / "evidence") as collector:
        data = json.dumps(otlp()).encode()
        for _ in range(2):
            request = urllib.request.Request(
                collector.endpoint, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(request) as response:
                assert response.status == 200
        collector.harvest_native(native)
        result = collector.finalize(exit_kind="completed")
        assert result["agent_turns"]["responses"]["value"] == 1
        assert "native_journal_unreadable" in result["usage"]["reasons"]
    assert "DO_NOT_RETAIN" not in (tmp_path / "evidence" / "observations.events.jsonl").read_text()


def test_http_receiver_rejects_oversize_payload_with_visible_completeness(tmp_path):
    with CodexTelemetryCollector(tmp_path, max_body_bytes=12) as collector:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(collector.endpoint, data=b"x" * 13))
        assert error.value.code == 413
        assert (
            "otel_request_size_invalid"
            in collector.finalize(exit_kind="failed")["usage"]["reasons"]
        )


def test_collector_configuration_uses_external_network_relay_endpoint_without_prompts(tmp_path):
    with CodexTelemetryCollector(tmp_path) as collector:
        text = collector.config_toml("http://relay:9000/v1/logs/qualification")
        import tomllib

        config = tomllib.loads(text)["otel"]
        assert config["log_user_prompt"] is False
        assert config["exporter"]["otlp-http"]["protocol"] == "json"
        with pytest.raises(ValueError):
            collector.config_toml("file:///auth.json")


def test_request_prices_use_each_request_context_not_aggregate_context():
    requests = [
        {
            "response_id": str(n),
            "thread_id": "thread-1",
            "model": "gpt-6-astra",
            "usage": usage(200000, 20000, 100, 1000),
        }
        for n in range(2)
    ]
    rows = price_requests(requests)
    assert not any(row["long_context"] for row in rows)
    assert sum(Decimal(row["usd"]) for row in rows) == Decimal("3.655")
    requests[0]["usage"] = usage(272001, 20000, 100, 1000)
    assert price_requests(requests)[0]["long_context"] is True
    requests[0]["usage"] = usage(272000, 20000, 100, 1000)
    assert price_requests(requests)[0]["long_context"] is False


def test_published_gpt54_session_context_rule_is_recorded_and_applied():
    rows = price_requests(
        [
            {"response_id": "a", "thread_id": "one", "model": "gpt-5.4", "usage": usage(300000)},
            {"response_id": "b", "thread_id": "one", "model": "gpt-5.4", "usage": usage(100)},
            {"response_id": "c", "thread_id": "two", "model": "gpt-5.4", "usage": usage(100)},
        ]
    )
    assert [r["long_context"] for r in rows] == [True, True, False]
    assert rows[1]["context_scope"] == "session"


@pytest.mark.parametrize(
    "changes",
    [
        {"cached_input_tokens": None},
        {"input_tokens": -1},
        {"output_tokens": True},
        {"cached_input_tokens": 500},
    ],
)
def test_unusable_usage_does_not_become_a_zero_cost(changes):
    row = price_requests(
        [{"response_id": "a", "model": "gpt-6-astra", "usage": {**usage(), **changes}}]
    )[0]
    assert row["usd"] is None
    assert row["reasons"]


def test_price_table_is_reproducible_and_carries_source_and_assumptions():
    assert price_table_metadata() == price_table_metadata()
    assert len(price_table_metadata()["sha256"]) == 64
    assert price_table_metadata()["models"]["gpt-6-astra"]["source"].startswith(
        "https://developers.openai.com/"
    )


def test_malformed_native_line_preserves_good_observations_and_marks_partial():
    events, reasons = normalize_rollout([*journal(), '{"truncated":'])
    result = summarize_events(events, exit_kind="completed", collection_reasons=reasons)
    assert result["usage"]["value"]["input_tokens"] == 100
    assert result["usage"]["completeness"] == "partial"


def test_forked_journal_cannot_reassign_child_activity_to_inherited_parent_metadata():
    child = [
        record("session_meta", {"id": "child", "cli_version": "0.153.4"}, 20),
        record("session_meta", {"id": "parent", "cli_version": "0.153.4"}, 0),
        record("turn_context", {"model": "gpt-5.4"}, 1),
        record(
            "response_item",
            {"type": "function_call", "name": "spawn_agent", "call_id": "old-call"},
            2,
        ),
        record("event_msg", {"type": "task_started", "turn_id": "child-turn"}, 21),
        record("turn_context", {"model": "gpt-5.4"}, 22),
        record(
            "response_item",
            {"type": "function_call", "name": "exec_command", "call_id": "child-call"},
            23,
        ),
        record(
            "token_usage_record",
            {"response_id": "child-response", "thread_id": "child", "usage": usage()},
            24,
        ),
        record("event_msg", {"type": "task_complete", "turn_id": "child-turn"}, 25),
    ]
    events, _ = normalize_rollout(child)
    result = summarize_events(events, exit_kind="completed")
    assert result["agent_turns"]["tool_calls"]["value"] == 1
    assert {e["thread_id"] for e in events} == {"child"}


def test_failed_transport_without_observed_usage_does_not_invent_zero_cost():
    events, _ = normalize_rollout(journal(response=None))
    result = summarize_events(events, exit_kind="failed")
    assert result["agent_turns"]["responses"]["value"] == 0
    assert result["usage"]["value"] is None
    assert result["estimated_cost"]["value"] is None


def test_otel_only_capture_preserves_known_usage_and_cost_as_partial():
    events = normalize_otlp(
        otlp(
            kind="response.completed",
            input_token_count="100",
            cached_token_count="20",
            cache_write_token_count="0",
            output_token_count="30",
            reasoning_token_count="5",
            tool_token_count="130",
        )
    )
    result = summarize_events(events, exit_kind="completed")
    assert result["usage"]["value"]["input_tokens"] == 100
    assert result["estimated_cost"]["value"] == "0.000655"
    assert result["estimated_cost"]["completeness"] == "partial"


def test_inherited_tool_call_is_deduplicated_by_original_turn_and_call():
    base = journal(thread="parent") + [
        record(
            "response_item",
            {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "shared-call",
                "internal_chat_message_metadata_passthrough": {"turn_id": "original-turn"},
            },
        )
    ]
    inherited = journal(thread="child", response="child-response") + [
        record(
            "response_item",
            {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "shared-call",
                "internal_chat_message_metadata_passthrough": {"turn_id": "original-turn"},
            },
        )
    ]
    first, _ = normalize_rollout(base)
    second, _ = normalize_rollout(inherited)
    assert (
        summarize_events(first + second, exit_kind="completed")["agent_turns"]["tool_calls"][
            "value"
        ]
        == 1
    )


def test_missing_reasoning_breakdown_does_not_make_exact_total_token_price_unknown():
    events, _ = normalize_rollout(journal())
    request = next(e for e in events if e["kind"] == "response")
    request["usage"]["reasoning_output_tokens"] = None
    result = summarize_events(events, exit_kind="completed")
    assert result["usage"]["completeness"] == "partial"
    assert result["estimated_cost"]["completeness"] == "complete"


def test_current_epoch_nanoseconds_preserve_distinct_events_in_one_millisecond():
    first = normalize_otlp(otlp(nanos=1790420000000000001))[0]
    second = normalize_otlp(otlp(nanos=1790420000000000002))[0]
    assert first["observed_ns"] == 1790420000000000001
    assert first["id"] != second["id"]


def test_streaming_fragments_are_not_retained_or_counted():
    assert normalize_otlp(otlp(kind="response.output_text.delta")) == []
    assert normalize_otlp(otlp(kind="response.output_item.done")) == []


@pytest.mark.parametrize(
    "scenario",
    [
        "basic",
        "tool_error",
        "retry",
        "export_retry",
        "interruption",
        "killed_response",
        "compaction",
        "descendant",
    ],
)
@pytest.mark.parametrize("fixture_name", ["karn_observations", "karn_observations_codex_0.157.1"])
def test_replay_actual_pinned_binary_qualification_matches_scripted_ground_truth(
    scenario, fixture_name
):
    import hashlib
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / fixture_name
    proof = json.loads((fixture / "qualification.json").read_text())
    assert proof["native_binary"].removeprefix("codex-cli ") in QUALIFIED_CODEX_VERSIONS
    expected = proof["scenarios"][scenario]
    raw = (fixture / (scenario + ".jsonl")).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected["events_sha256"]
    events = [json.loads(line) for line in raw.splitlines()]
    result = summarize_events(events, exit_kind=expected["coverage"]["exit_kind"])
    assert result["agent_turns"] == expected["agent_turns"]
    assert result["agent_turns"]["responses"]["value"] == expected["scripted_responses"]
    assert result["agent_turns"]["tool_calls"]["value"] == expected["scripted_tool_calls"]
    assert result["usage"] == expected["usage"]
    assert result["estimated_cost"] == expected["estimated_cost"]
    for event in events:
        assert not (
            {"prompt", "arguments", "output", "user.email", "authorization"}
            & set(event.get("attributes", {}))
        )


def test_cost_breakdown_tallies_each_input_type_and_sums_to_the_request_price():
    rows = price_requests(
        [
            {
                "response_id": "r",
                "model": "gpt-6-astra",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 20,
                    "cache_write_input_tokens": 7,
                    "output_tokens": 30,
                },
            }
        ]
    )
    parts = rows[0]["breakdown"]
    assert {name: part["tokens"] for name, part in parts.items()} == {
        "uncached_input": 73,
        "cache_read": 20,
        "cache_write": 7,
        "cache_write_1h": 0,
        "output": 30,
    }
    assert sum(Decimal(part["usd"]) for part in parts.values()) == Decimal(rows[0]["usd"])


def claude_request(written_1h, **usage_changes):
    usage_values = {
        "input_tokens": 1000 + 4000 + 300,
        "cached_input_tokens": 4000,
        "cache_write_input_tokens": 300,
        "cache_write_1h_input_tokens": written_1h,
        "output_tokens": 50,
        **usage_changes,
    }
    return {"response_id": "c", "model": "claude-opus-5-5", "usage": usage_values}


def test_anthropic_five_minute_and_one_hour_writes_price_separately():
    row = price_requests([claude_request(100)])[0]
    parts = row["breakdown"]
    # Opus 5.5: input $4, 5m write $5, 1h write $8, read $0.20 (0.05x), output $20 per MTok.
    assert parts["uncached_input"] == {"tokens": 1000, "usd": "0.004"}
    assert parts["cache_read"] == {"tokens": 4000, "usd": "0.0008"}
    assert parts["cache_write"] == {"tokens": 200, "usd": "0.001"}
    assert parts["cache_write_1h"] == {"tokens": 100, "usd": "0.0008"}
    assert parts["output"] == {"tokens": 50, "usd": "0.001"}
    assert Decimal(row["usd"]) == Decimal("0.0076")


def test_fable_is_priced_from_anthropic_rates():
    row = price_requests([{**claude_request(100), "model": "claude-fable-5-1"}])[0]
    parts = row["breakdown"]
    # Fable 5.1: input $10, 5m write $12.50, 1h write $20, read $0.25 (0.025x), output $50.
    expected = {
        "uncached_input": (1000, "0.01"),
        "cache_read": (4000, "0.001"),
        "cache_write": (200, "0.0025"),
        "cache_write_1h": (100, "0.002"),
        "output": (50, "0.0025"),
    }
    for kind, (tokens, usd) in expected.items():
        assert parts[kind]["tokens"] == tokens
        assert Decimal(parts[kind]["usd"]) == Decimal(usd)
    assert Decimal(row["usd"]) == Decimal("0.018")


def test_unknown_one_hour_split_is_not_priced_at_either_rate():
    row = price_requests([claude_request(None)])[0]
    assert row["usd"] is None
    assert row["reasons"] == ["cache_write_split_missing_or_invalid"]
    no_writes = price_requests(
        [claude_request(None, input_tokens=5000, cache_write_input_tokens=0)]
    )
    assert no_writes[0]["usd"] is not None


@pytest.mark.parametrize(
    ("field", "tier"), [("speed", "fast"), ("service_tier", "priority"), ("service_tier", "flex")]
)
def test_every_tier_is_priced_at_standard_rates(field, tier):
    standard = price_requests([claude_request(0)])[0]
    row = price_requests([{**claude_request(0), field: tier}])[0]
    assert row["reasons"] == []
    assert row["usd"] == standard["usd"]
    assert row["rate_basis"] == "standard"


def test_unknown_models_stay_unpriced_whatever_their_tier():
    row = price_requests([{**claude_request(0), "model": "future-model", "service_tier": "flex"}])[
        0
    ]
    assert row["usd"] is None
    assert row["reasons"] == ["model_price_unavailable"]


def completed_otlp(nanos, **attrs):
    return otlp(
        kind="response.completed",
        nanos=nanos,
        input_token_count="100",
        cached_token_count="20",
        cache_write_token_count="0",
        output_token_count="30",
        reasoning_token_count="5",
        tool_token_count="130",
        **attrs,
    )


def test_codex_rows_record_the_tier_codex_requested():
    native, _ = normalize_rollout(journal())
    standard = summarize_events(native, exit_kind="completed")
    flex = summarize_events(
        native + normalize_otlp(completed_otlp(1, service_tier="flex")), exit_kind="completed"
    )
    assert [r["requested_service_tier"] for r in standard["requests"]] == [None]
    assert [r["requested_service_tier"] for r in flex["requests"]] == ["flex"]
    # Recorded, never repriced: the estimate stays at standard rates.
    assert flex["estimated_cost"]["value"] == standard["estimated_cost"]["value"]
    mixed = summarize_events(
        native
        + normalize_otlp(completed_otlp(1, service_tier="flex"))
        + normalize_otlp(completed_otlp(2, service_tier="priority")),
        exit_kind="completed",
    )
    assert [r["requested_service_tier"] for r in mixed["requests"]] == ["mixed"]


def test_an_unrecognized_codex_tier_is_kept_only_as_unknown():
    [event] = normalize_otlp(completed_otlp(1, service_tier="sk-live-token-lookalike"))
    assert event["attributes"]["service_tier"] == "unknown"
    otel_only = summarize_events([event], exit_kind="completed")
    assert [r["requested_service_tier"] for r in otel_only["requests"]] == ["unknown"]
    assert otel_only["estimated_cost"]["value"] is not None


def test_summary_reports_the_cost_breakdown_beside_the_estimate():
    events, _ = normalize_rollout(journal())
    result = summarize_events(events, exit_kind="completed")
    breakdown = result["cost_breakdown"]
    assert breakdown["completeness"] == result["estimated_cost"]["completeness"]
    assert sum(Decimal(part["usd"]) for part in breakdown["value"].values()) == Decimal(
        result["estimated_cost"]["value"]
    )


@pytest.mark.parametrize(("scenario", "expected"), [("basic", 0), ("descendant", 1)])
def test_codex_subagent_threads_count_threads_beyond_the_main_one(scenario, expected):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "karn_observations_codex_0.157.1"
    raw = (fixture / (scenario + ".jsonl")).read_bytes()
    events = [json.loads(line) for line in raw.splitlines()]
    assert summarize_events(events, exit_kind="completed")["subagent_threads"] == expected


def test_subagent_threads_are_missing_without_observations():
    assert summarize_events([], exit_kind="completed")["subagent_threads"] is None
