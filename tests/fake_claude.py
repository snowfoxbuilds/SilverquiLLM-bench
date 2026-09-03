"""A scripted stand-in for the Claude Code CLI, launched by the REAL harness.

The production harness invokes its adapter's headless one-shot argv —
``claude -p <pointer> --dangerously-skip-permissions --output-format
stream-json --verbose`` — in the manifest's workdir with ``THEOZOLITH_JOB``
set.  The conformance tests put this program on ``PATH`` as ``claude``.  It
behaves like a well-formed session: it resolves the pointer to the task file,
reads the production-rendered task, emits a stream-json transcript on stdout,
acts on a JSON playbook (``$SQM_FAKE_CLAUDE_PLAYBOOK``), and writes its Output
Proposal through the real ``format-output`` CLI — never ``proposal.json`` by
hand.

Playbook keys (all optional):

- ``implement``: collector numbers whose HOB reference ``card_impl.py`` to copy
  into ``cards/fdn/fdn_<n>/`` (the workdir is the checkout).
- ``write_files``: ``{relative path: content}`` written under the workdir
  (files under a ``hooks/`` directory are made executable).
- ``git_config``: ``{key: value}`` set with ``git config`` in the workdir.
- ``symlinks``: ``{relative link: target}`` created under the workdir.
- ``proposal``: ``{field: value}`` written via ``format-output``, in order.
- ``record_invocation_to``: a path to write the invocation facts to as JSON.
- ``hang_seconds``: sleep this long before exiting (for the timeout tests).
- ``exit_code``: the process exit code (default 0).

Standalone on purpose: it imports nothing from the bench package.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOB_FDN = REPO / "benchmarks" / "hob-medium" / "workspace" / "cards" / "fdn"
PLAYBOOK_ENV = "SQM_FAKE_CLAUDE_PLAYBOOK"

# The harness's constant pointer prompt (ADR-0019 as amended).
POINTER_RE = re.compile(
    r"\AWork on the task specified in (?P<path>\S+)\. Read that file first"
)
EXPECTED_FLAGS = ["--dangerously-skip-permissions", "--output-format", "stream-json", "--verbose"]


def _emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _fail(message: str, code: int) -> int:
    _emit({"type": "error", "error": message})
    return code


def main(argv: list[str]) -> int:
    if "-p" not in argv or argv.index("-p") + 1 >= len(argv):
        return _fail("no -p pointer prompt in argv", 3)
    pointer = argv[argv.index("-p") + 1]
    match = POINTER_RE.match(pointer)
    if match is None:
        return _fail(f"argv carries task content, not the constant pointer: {pointer!r}", 3)
    task_path = Path(match.group("path"))
    try:
        task = task_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _fail(f"cannot read the task file {task_path}: {exc}", 3)
    playbook = json.loads(Path(os.environ[PLAYBOOK_ENV]).read_text(encoding="utf-8"))
    workdir = Path.cwd()

    _emit({"type": "system", "subtype": "init", "model": "fake-claude"})
    record = playbook.get("record_invocation_to")
    if record:
        Path(record).write_text(
            json.dumps(
                {
                    "argv": argv,
                    "flags_after_pointer": argv[argv.index("-p") + 2 :],
                    "cwd": str(workdir),
                    "job": os.environ.get("THEOZOLITH_JOB"),
                    "task_path": str(task_path),
                    "task_is_implementer_prompt": "Implementer in TheOzolith" in task,
                    "task_mentions_format_output": "format-output" in task,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    for cn in playbook.get("implement", []):
        target = workdir / "cards" / "fdn" / f"fdn_{cn}" / "card_impl.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOB_FDN / f"fdn_{cn}" / "card_impl.py", target)
    for rel, content in playbook.get("write_files", {}).items():
        path = workdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if "hooks" in path.parts:
            path.chmod(0o755)
    for key, value in playbook.get("git_config", {}).items():
        subprocess.run(["git", "config", key, value], cwd=workdir, check=True)
    for rel, target in playbook.get("symlinks", {}).items():
        link = workdir / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, link)
    for field, value in playbook.get("proposal", {}).items():
        proc = subprocess.run(
            ["format-output", field, value], capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            return _fail(f"format-output {field} failed: {proc.stderr.strip()}", 4)

    _emit(
        {
            "type": "assistant",
            "message": {
                "model": "fake-claude",
                "content": [{"type": "text", "text": "done"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        }
    )
    _emit(
        {
            "type": "result",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "modelUsage": {"fake-claude": {}},
        }
    )
    hang = float(playbook.get("hang_seconds", 0) or 0)
    if hang:
        time.sleep(hang)
    return int(playbook.get("exit_code", 0))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
