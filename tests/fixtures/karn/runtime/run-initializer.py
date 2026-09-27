"""Run the declared initializer, then replace this process with the main command."""

import argparse
import json
import os
import signal
import subprocess
import sys
from contextlib import suppress


def run(initializer, command):
    if not all(
        isinstance(argv, list)
        and argv
        and argv[0]
        and all(isinstance(arg, str) and "\0" not in arg for arg in argv)
        for argv in (initializer, command)
    ):
        raise ValueError("initializer and main must be executable argument arrays")
    child = None
    pending = []
    previous = {}

    def forward(number, _frame):
        pending.append(number)
        if child is not None:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, number)

    try:
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            previous[number] = signal.signal(number, forward)
        child = subprocess.Popen(initializer, start_new_session=True)
        if pending:
            forward(pending[-1], None)
        result = child.wait()
        if pending:
            return 128 + pending[-1]
        if result:
            return result if result > 0 else 128 - result
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    os.execvpe(command[0], command, os.environ)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run-initializer")
    parser.add_argument("--initializer-json", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        return run(json.loads(args.initializer_json), command)
    except (ValueError, OSError) as error:
        print(f"run-initializer: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
