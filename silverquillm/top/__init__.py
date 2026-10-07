"""``silverquillm top``: the read-only terminal monitor (RUN-MONITORING.md).

Textual is the optional ``monitor`` extra, so nothing here imports it until the app starts.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

INSTALL_HINT = "silverquillm top needs the monitor extra: pip install 'silverquillm-bench[monitor]'"
NO_TERMINAL = (
    "silverquillm top needs a terminal; for a one-shot listing use `silverquillm queue ls`"
    " (add --json for scripts)"
)


def textual_available() -> bool:
    return importlib.util.find_spec("textual") is not None


def launch(
    given: Mapping[str, Path | None],
    *,
    interval: float = 2.0,
    no_flair: bool = False,
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
    try:
        look, notice = theme_named(monitor.config.theme, no_flair=no_flair)
        build_app(monitor, look, interval=interval, notice=notice).run()
    finally:
        monitor.close()
    return 0
