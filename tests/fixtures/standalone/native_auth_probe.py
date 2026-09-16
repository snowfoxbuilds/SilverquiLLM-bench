"""Observe native API-key selection against loopback only; never request vendor inference."""

import hashlib
import http.server
import json
import os
import subprocess
import threading
from pathlib import Path

observed = []
expected = os.environ["EXPECTED_DIGEST"]
adapter = os.environ["PROBE_ADAPTER"]


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        value = (
            self.headers.get("x-api-key", "")
            if adapter == "claude"
            else self.headers.get("Authorization", "").removeprefix("Bearer ")
        )
        observed.append(hashlib.sha256(value.encode()).hexdigest() == expected)
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = b'{"error":{"message":"offline credential fixture","type":"authentication_error"}}'
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever)
thread.start()
base = "http://127.0.0.1:" + str(server.server_port)
environ = dict(os.environ)
if adapter == "codex":
    command = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "--json",
        "--model",
        os.environ["BENCHMARK_MODEL"],
        "-c",
        'openai_base_url="' + base + '/v1"',
        "-",
    ]
else:
    environ["ANTHROPIC_BASE_URL"] = base
    environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    command = ["claude", "-p", "--model", os.environ["BENCHMARK_MODEL"]]
try:
    try:
        result = subprocess.run(
            command,
            input="Offline authentication fixture; do not execute tools.",
            env=environ,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        exit_code = "timeout"
finally:
    server.shutdown()
    server.server_close()
    thread.join()
if not any(observed):
    diagnostic = result.stderr[-2000:] if exit_code != "timeout" else "native CLI timed out"
    for key in ("CODEX_API_KEY", "ANTHROPIC_API_KEY"):
        if os.environ.get(key):
            diagnostic = diagnostic.replace(os.environ[key], "[redacted]")
    raise RuntimeError("native API-key selection was not observed: " + diagnostic)
Path("/workspace/native-auth.json").write_text(
    json.dumps(
        {
            "matched": True,
            "requests": len(observed),
            "exit": exit_code,
            "upstream": "loopback fixture only",
        }
    )
)
Path("/output/proposal.json").write_text(
    json.dumps(
        {
            "schema_version": 1,
            "mode": "run",
            "fields": {
                "pr-title": "Qualify native API-key selection",
                "pr-description": "Local rejecting endpoint, no vendor inference.",
                "commit-message": "Qualify native API-key selection",
                "decisions": [
                    {
                        "what": "Use a loopback rejecting endpoint",
                        "why": "Observe credentials without vendor calls.",
                    }
                ],
            },
        }
    )
)
