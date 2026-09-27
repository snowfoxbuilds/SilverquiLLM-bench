#!/usr/bin/env python3
"""Exercise the pinned Codex binary using only scripted loopback HTTP responses.

The outer process starts a network-disabled container, with no user credential
or native-home mounts. Only sanitized accounting observations leave it.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# The candidate image lacks the bench's dependencies, so load only the stdlib-only
# observations module without running silverquillm.karn's package imports.
_karn = types.ModuleType("silverquillm.karn")
_karn.__path__ = [str(Path(__file__).resolve().parents[1] / "silverquillm/karn")]
sys.modules.setdefault("silverquillm.karn", _karn)
from silverquillm.karn.observations import CodexTelemetryCollector

IMAGE = "sha256:a8b10ff219d5d81870c1b17eae9dbe0eb7494db1c8bd08adcb174b927b569cd6"
SCENARIOS = (
    "basic",
    "tool_error",
    "retry",
    "export_retry",
    "interruption",
    "killed_response",
    "compaction",
    "descendant",
)


class ScriptedProvider:
    def __init__(self, scenario, collector):
        self.scenario, self.collector = scenario, collector
        self.requests = []
        self.attempts = self.exports = 0
        self.root = None
        self.thread_requests = Counter()
        self.tools = set()
        self.lock = threading.Lock()

    def handle(self, path, body):
        if not path.endswith("/responses"):
            return 200, "application/json", b"{}"
        with self.lock:
            self.attempts += 1
            if self.scenario == "retry" and self.attempts == 1:
                return (
                    503,
                    "application/json",
                    b'{"error":{"message":"synthetic retry","type":"server_error"}}',
                )
            meta = body.get("client_metadata", {})
            thread = meta.get("thread_id", "unknown")
            if self.root is None:
                self.root = thread
            self.thread_requests[thread] += 1
            local_n = self.thread_requests[thread]
            number = len(self.requests) + 1
            is_compaction = any(
                item.get("type") == "compaction_trigger" for item in body.get("input", [])
            )
            tool_rows = {row.get("name"): row for row in body.get("tools", []) if row.get("name")}
            for row in list(tool_rows.values()):
                if row.get("type") == "namespace":
                    for tool in row.get("tools", []):
                        tool_rows[row["name"] + "." + tool["name"]] = tool
            self.tools.update(tool_rows)
            self.requests.append(
                {"response_id": f"resp_{number}", "thread_id": thread, "compaction": is_compaction}
            )
        item = {
            "id": f"msg_{number}",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [
                {"type": "output_text", "text": "Synthetic completion.", "annotations": []}
            ],
        }
        if is_compaction:
            item = {"type": "compaction", "id": f"cmp_{number}", "encrypted_content": "synthetic"}
        elif self.scenario in ("tool_error", "compaction", "interruption") and number == 1:
            item = self.call(
                number,
                "exec_command",
                {
                    "cmd": "sleep 30" if self.scenario == "interruption" else "exit 7",
                    "yield_time_ms": 10000,
                    "max_output_tokens": 32,
                },
            )
        elif self.scenario == "descendant":
            if thread == self.root and local_n == 1:
                item = self.call(number, "exec_command", {"cmd": "true", "max_output_tokens": 32})
            elif thread == self.root and local_n == 2:
                name = next((name for name in tool_rows if "spawn_agent" in name), None)
                if not name:
                    raise RuntimeError(
                        "pinned_binary_exposes_no_spawn_tool:"
                        + repr(
                            [
                                {
                                    k: (
                                        v
                                        if k in ("type", "name", "namespace")
                                        else type(v).__name__
                                    )
                                    for k, v in row.items()
                                }
                                for row in body.get("tools", [])
                            ]
                        )
                    )
                props = tool_rows[name].get("parameters", {}).get("properties", {})
                args = {"message": "Perform the scripted offline child task."}
                if "task_name" in props:
                    args["task_name"] = "qualification_child"
                item = self.call(number, name, args)
            elif thread == self.root and local_n == 3:
                name = next(
                    (
                        name
                        for name in tool_rows
                        if name.rsplit(".", 1)[-1] in ("wait", "wait_agent")
                    ),
                    None,
                )
                outputs = [
                    i.get("output")
                    for i in body.get("input", [])
                    if i.get("type") == "function_call_output"
                ]
                child = None
                for value in outputs:
                    try:
                        decoded = json.loads(value)
                        child = decoded.get("agent_id") or decoded.get("id") or child
                    except (TypeError, ValueError):
                        pass
                if not name:
                    raise RuntimeError("spawn_output_not_understood")
                props = tool_rows[name].get("parameters", {}).get("properties", {})
                args = {}
                if "ids" in props:
                    if not child:
                        raise RuntimeError("spawn_child_id_unavailable")
                    args["ids"] = [child]
                elif "agent_ids" in props:
                    args["agent_ids"] = [child]
                if "timeout_ms" in props:
                    args["timeout_ms"] = 10000
                item = self.call(number, name, args)
            elif thread != self.root and local_n == 1:
                item = self.call(number, "exec_command", {"cmd": "true", "max_output_tokens": 32})
        provider_record = self.requests[number - 1]
        provider_record["tool_call"] = item["type"] == "function_call"
        response = {
            "id": f"resp_{number}",
            "object": "response",
            "status": "completed",
            "model": "gpt-5.4",
            "output": [item],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 30,
                "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 7},
                "output_tokens_details": {"reasoning_tokens": 5},
                "total_tokens": 130,
            },
        }
        events = [
            {
                "type": "response.created",
                "response": {**response, "status": "in_progress", "output": []},
            },
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": response},
        ]
        if item["type"] == "message":
            fragments = [
                {
                    "type": "response.output_text.delta",
                    "item_id": item["id"],
                    "output_index": 0,
                    "content_index": 0,
                    "delta": text,
                }
                for text in ("Synthetic ", "completion.")
            ]
            events[1:1] = fragments
        if self.scenario == "killed_response":
            events = events[:1]
        data = "".join(
            "event: " + e["type"] + "\ndata: " + json.dumps(e) + "\n\n" for e in events
        ).encode()
        return 200, "text/event-stream", data

    @staticmethod
    def call(number, name, arguments):
        namespace, _, leaf = name.rpartition(".")
        item = {
            "type": "function_call",
            "id": f"fc_{number}",
            "call_id": f"call_{number}",
            "name": leaf or name,
            "arguments": json.dumps(arguments),
        }
        if namespace:
            item["namespace"] = namespace
        return item


class ProviderServer(ThreadingHTTPServer):
    daemon_threads = True


def qualify_one(scenario: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with CodexTelemetryCollector(output) as collector:
        provider = ScriptedProvider(scenario, collector)
        errors = []
        release_stream = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(400)
                self.end_headers()

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    if self.path == "/retry-logs":
                        provider.exports += 1
                        collector.ingest_otlp(body)
                        status = 503 if provider.exports == 1 else 200
                        content_type, data = "application/json", b"{}"
                    else:
                        status, content_type, data = provider.handle(self.path, body)
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    if scenario != "killed_response" or not self.path.endswith("/responses"):
                        self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    self.wfile.flush()
                    if scenario == "killed_response" and self.path.endswith("/responses"):
                        release_stream.wait(30)
                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                    errors.append(type(exc).__name__ + ":" + str(exc))
                    self.send_error(500)

        server = ProviderServer(("127.0.0.1", 0), Handler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        process = None
        try:
            with tempfile.TemporaryDirectory(prefix="codex-qualification-") as temp:
                root = Path(temp)
                native, workspace = root / "native", root / "workspace"
                native.mkdir()
                workspace.mkdir()
                endpoint = f"http://127.0.0.1:{server.server_port}"
                selected_model = "gpt-5.4"
                config = f'model = "{selected_model}"\nmodel_reasoning_effort = "low"\n'
                if scenario == "compaction":
                    config += f'openai_base_url = "{endpoint}/v1"\nmodel_auto_compact_token_limit = 120\nmodel_context_window = 20000\n'
                else:
                    config += (
                        'model_provider = "qualification"\n'
                        '[model_providers.qualification]\nname = "Offline qualification"\n'
                        f'base_url = "{endpoint}/v1"\nwire_api = "responses"\n'
                        'env_key = "QUALIFICATION_API_KEY"\nrequest_max_retries = 1\nstream_max_retries = 0\n'
                    )
                telemetry = (
                    endpoint + "/retry-logs" if scenario == "export_retry" else collector.endpoint
                )
                config += collector.config_toml(telemetry)
                config += "[analytics]\nenabled = false\n[feedback]\nenabled = false\n[features]\nshell_snapshot = false\nmulti_agent = true\nmulti_agent_v2 = true\n"
                (native / "config.toml").write_text(config)
                environment = {
                    "PATH": os.environ["PATH"],
                    "HOME": str(root / "empty-home"),
                    "CODEX_HOME": str(native),
                    "QUALIFICATION_API_KEY": "offline-dummy",
                    "CODEX_API_KEY": "offline-dummy",
                    "OTEL_BLRP_SCHEDULE_DELAY": "50",
                }
                argv = [
                    "codex",
                    "exec",
                    "--json",
                    "--skip-git-repo-check",
                    "--dangerously-bypass-approvals-and-sandbox",
                    "--cd",
                    str(workspace),
                    "-",
                ]
                process = subprocess.Popen(
                    argv,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=environment,
                    start_new_session=True,
                )
                if scenario in ("interruption", "killed_response"):
                    process.stdin.write("Execute the scripted synthetic qualification.\n")
                    process.stdin.close()
                    process.stdin = None
                    deadline = time.monotonic() + 20
                    while process.poll() is None and time.monotonic() < deadline:
                        if any(
                            e["kind"] == "codex.tool_decision"
                            or (
                                scenario == "killed_response"
                                and e.get("attributes", {}).get("event.kind") == "response.created"
                            )
                            for e in collector.events
                        ):
                            break
                        time.sleep(0.05)
                    os.killpg(
                        process.pid,
                        signal.SIGKILL if scenario == "killed_response" else signal.SIGINT,
                    )
                    release_stream.set()
                    stdout, stderr = process.communicate(timeout=15)
                else:
                    stdout, stderr = process.communicate(
                        "Execute the scripted synthetic qualification.\n", timeout=45
                    )
                collector.harvest_native(native)
                result = collector.finalize(
                    exit_kind="interrupted"
                    if scenario in ("interruption", "killed_response")
                    else "completed"
                    if process.returncode == 0
                    else "failed",
                    native_version="0.153.4",
                )
                stream_types = Counter()
                for line in stdout.splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    stream_types[event.get("type", "unknown")] += 1
                expected_tools = sum(bool(r.get("tool_call")) for r in provider.requests)
                if result["agent_turns"]["responses"]["value"] != len(provider.requests):
                    errors.append("response_accounting_does_not_match_scripted_provider")
                if result["agent_turns"]["tool_calls"]["value"] != expected_tools:
                    errors.append("tool_accounting_does_not_match_scripted_provider")
                if scenario == "export_retry" and provider.exports < 2:
                    errors.append("export_retry_not_observed")
                if scenario != "killed_response":
                    expected_usage = {
                        "input_tokens": 100 * len(provider.requests),
                        "cached_input_tokens": 20 * len(provider.requests),
                        "cache_write_input_tokens": 7 * len(provider.requests),
                        "output_tokens": 30 * len(provider.requests),
                        "reasoning_output_tokens": 5 * len(provider.requests),
                        "total_tokens": 130 * len(provider.requests),
                    }
                    if result["usage"]["value"] != expected_usage:
                        errors.append("token_accounting_does_not_match_scripted_provider")
                summary = {
                    "scenario": scenario,
                    "exit_code": process.returncode,
                    "scripted_responses": len(provider.requests),
                    "scripted_tool_calls": expected_tools,
                    "http_attempts": provider.attempts,
                    "export_attempts": provider.exports,
                    "provider_threads": len(provider.thread_requests),
                    "native_event_types": dict(stream_types),
                    "provider_errors": errors,
                    "agent_turns": result["agent_turns"],
                    "usage": result["usage"],
                    "estimated_cost": result["estimated_cost"],
                    "coverage": result["coverage"],
                    "stderr_present": bool(stderr),
                    "tool_names": sorted(provider.tools),
                }
                (output / "qualification.json").write_text(
                    json.dumps(summary, indent=2, sort_keys=True) + "\n"
                )
                return summary
        finally:
            release_stream.set()
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=SCENARIOS, action="append")
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--native-version", default="0.153.4")
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    scenarios = args.scenario or list(SCENARIOS)
    if not args.inside:
        root = Path(__file__).resolve().parents[1]
        args.output.mkdir(parents=True, exist_ok=True)
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--mount",
            f"type=bind,src={root},dst=/qualification,readonly",
            "--mount",
            f"type=bind,src={args.output.resolve()},dst=/evidence",
            "--entrypoint",
            "python3",
            args.image,
            "/qualification/scripts/qualify_codex_telemetry.py",
            "--inside",
            "--output",
            "/evidence",
            "--native-version",
            args.native_version,
        ]
        for scenario in scenarios:
            command += ["--scenario", scenario]
        return subprocess.run(command, check=False).returncode
    native = subprocess.run(
        ["codex", "--version"], text=True, capture_output=True, check=True
    ).stdout.strip()
    if native != "codex-cli " + args.native_version:
        raise RuntimeError("qualification requires codex-cli " + args.native_version)
    results = [qualify_one(scenario, args.output / scenario) for scenario in scenarios]
    proof = {
        "binary": native,
        "network": "none; loopback-only scripted Responses and OTLP",
        "real_credentials": False,
        "paid_inference": False,
        "results": results,
    }
    (args.output / "qualification.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(proof, sort_keys=True))
    failed = [
        r
        for r in results
        if r["provider_errors"]
        or (r["scenario"] not in ("interruption", "killed_response") and r["exit_code"] != 0)
    ]
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
