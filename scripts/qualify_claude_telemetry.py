#!/usr/bin/env python3
"""Qualify a pinned Claude Code version from a real run's sanitized observations.

Claude Code documents its transcript format as internal, so the bench trusts a version's
transcript accounting only after one real run shows the transcript and the OTel stream
agree: every transcript request has an ``api_request`` with the same token counts, every
other ``api_request`` is a compaction matching a transcript compaction boundary, and both
streams name the same tool calls. The run's ``observations.events.jsonl`` holds only
sanitized accounting fields, so it is the proof fixture itself.

    scripts/qualify_claude_telemetry.py runs/karn/<run-id> --out proof.json

A qualifying proof is committed with its events under
``tests/fixtures/karn_observations_claude_<version>/`` and the version is added to
``QUALIFIED_CLAUDE_VERSIONS``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silverquillm.karn.claude_observations import _otel_usage, summarize_claude_events

COMPARED = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens")


def qualify(raw: bytes) -> dict:
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    native = [e for e in events if e.get("source") == "native"]
    otel = [e for e in events if e.get("source") == "otel"]
    mismatches = []
    versions = {e.get("native_version") for e in native if e["kind"] == "session"} - {None}
    otel_versions = {e["attributes"].get("app.version") for e in otel} - {None}
    if len(versions) != 1:
        mismatches.append({"check": "single_native_version", "observed": sorted(versions)})
    if otel_versions - versions:
        mismatches.append({"check": "otel_version_matches", "observed": sorted(otel_versions)})
    requests = {
        e["attributes"].get("request_id"): e for e in otel if e["kind"] == "claude_code.api_request"
    }
    responses = [e for e in native if e["kind"] == "response"]
    for response in responses:
        match = requests.get(response.get("request_id"))
        if match is None:
            mismatches.append({"check": "request_in_otel", "request": response.get("request_id")})
            continue
        observed = _otel_usage(match["attributes"])
        for key in COMPARED:
            if observed[key] != response["usage"][key]:
                mismatches.append(
                    {
                        "check": "usage_agrees",
                        "request": response.get("request_id"),
                        "field": key,
                        "transcript": response["usage"][key],
                        "otel": observed[key],
                    }
                )
    known = {r.get("request_id") for r in responses}
    extra = [e for request, e in requests.items() if request not in known]
    compacting = [e for e in extra if e["attributes"].get("query_source") == "compact"]
    boundaries = [e for e in native if e["kind"] == "compaction"]
    if len(compacting) != len(extra):
        mismatches.append(
            {"check": "extra_requests_are_compactions", "observed": len(extra) - len(compacting)}
        )
    if len(compacting) != len(boundaries):
        mismatches.append(
            {
                "check": "compactions_agree",
                "transcript": len(boundaries),
                "otel": len(compacting),
            }
        )
    native_tools = {e["call_id"] for e in native if e["kind"] == "tool_call"}
    otel_tools = {
        e["attributes"].get("tool_use_id") for e in otel if e["kind"] == "claude_code.tool_result"
    } - {None}
    if native_tools != otel_tools:
        mismatches.append(
            {
                "check": "tool_calls_agree",
                "transcript_only": len(native_tools - otel_tools),
                "otel_only": len(otel_tools - native_tools),
            }
        )
    if not responses or not otel:
        mismatches.append({"check": "both_streams_present"})
    summary = summarize_claude_events(events, exit_kind="completed")
    return {
        "native_binary": "claude-code " + (min(versions) if versions else "unknown"),
        "events_sha256": hashlib.sha256(raw).hexdigest(),
        "paid_inference": True,
        "qualified": not mismatches,
        "mismatches": mismatches,
        "agent_turns": summary["agent_turns"],
        "usage": summary["usage"],
        "estimated_cost": summary["estimated_cost"],
        "cost_breakdown": summary["cost_breakdown"],
        "coverage": summary["coverage"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path)
    options = parser.parse_args()
    raw = (options.run_dir / "observations.events.jsonl").read_bytes()
    proof = qualify(raw)
    text = json.dumps(proof, indent=2, sort_keys=True) + "\n"
    if options.out:
        options.out.write_text(text)
    print(text, end="")
    return 0 if proof["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
