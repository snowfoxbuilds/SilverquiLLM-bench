"""Benchmark-owned native CLI file adapter; no runtime package imports."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("adapter", choices=("claude", "codex"))
    parser.add_argument(
        "--check", action="store_true", help="offline startup/file-interface qualification"
    )
    args = parser.parse_args(argv)
    request = json.loads(Path("/input/request.json").read_text())
    prompt = Path(request["prompt_path"]).read_text()
    output = Path(request["proposal_path"])
    workspace = Path(request["workspace_path"])
    if args.check:
        result = subprocess.run(
            [args.adapter, "--version"], capture_output=True, text=True, check=True
        )
        (workspace / "native-version.json").write_text(
            json.dumps(
                {
                    "adapter": args.adapter,
                    "version": result.stdout.strip(),
                    "uid": os.getuid(),
                    "gid": os.getgid(),
                    "prompt_bytes": len(prompt.encode()),
                }
            )
        )
        output.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "mode": "run",
                    "fields": {
                        "pr-title": "Qualify native startup",
                        "pr-description": "Offline CLI and file adapter qualification only.",
                        "commit-message": "Qualify native startup",
                        "decisions": [
                            {
                                "what": "Run the pinned native CLI offline",
                                "why": "Verify packaging and declared files without inference or login.",
                            }
                        ],
                    },
                }
            )
        )
        return 0
    model = os.environ["BENCHMARK_MODEL"]
    if args.adapter == "claude":
        command = [
            "claude",
            "-p",
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            model,
        ]
    else:
        command = [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--json",
            "--model",
            model,
            "-",
        ]
    return subprocess.run(command, input=prompt, text=True, cwd=workspace, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
