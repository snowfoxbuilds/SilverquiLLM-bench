"""``silverquillm top``: the read-only terminal monitor (RUN-MONITORING.md).

Textual is the optional ``monitor`` extra, so nothing here imports it until the app starts.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

INSTALL_HINT = "silverquillm top needs the monitor extra: pip install 'silverquillm-bench[monitor]'"
NO_TERMINAL = (
    "silverquillm top needs a terminal; for one machine-readable snapshot use"
    " `silverquillm top --json`"
)


def textual_available() -> bool:
    return importlib.util.find_spec("textual") is not None


def _driver():
    """Cell-coordinate mouse reporting on POSIX terminals (see ``terminal``)."""
    if sys.platform == "win32":
        return None
    from .terminal import CellMouseDriver

    return CellMouseDriver


def launch(
    given: Mapping[str, Path | None],
    *,
    interval: float = 2.0,
    no_flair: bool = False,
    mouse: bool = True,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the monitor until the operator quits; returns the process exit status."""
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    if not (stdin.isatty() and stdout.isatty()):
        print(NO_TERMINAL, file=stderr)
        return 1
    if not textual_available():
        print(INSTALL_HINT, file=stderr)
        return 1
    from silverquillm.monitor import Monitor

    from .app import build_app
    from .theme import theme_named

    monitor = Monitor(given={key: value for key, value in given.items() if value is not None})
    app = None
    try:
        look, notice = theme_named(monitor.config.theme, no_flair=no_flair)
        app = build_app(monitor, look, interval=interval, notice=notice, driver_class=_driver())
        app.run(mouse=mouse)
    finally:
        # The app closes the monitor once its last worker is done, never under one.
        if app is None:
            monitor.close()
        else:
            app.release_monitor()
    return 0


def print_snapshot(
    given: Mapping[str, Path | None], *, stdout: TextIO | None = None, **monitor_options
) -> int:
    """Write one snapshot of what the monitor shows as JSON; needs no terminal or extra."""
    from silverquillm.monitor import Monitor
    from silverquillm.monitor.headless import snapshot_document

    stdout = stdout or sys.stdout
    monitor = Monitor(
        given={key: value for key, value in given.items() if value is not None},
        **{"follow_output": False, "sample_usage": True, **monitor_options},
    )
    try:
        document = snapshot_document(monitor.snapshot())
    finally:
        monitor.close()
    json.dump(document, stdout, indent=2)
    stdout.write("\n")
    return 0
