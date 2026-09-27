"""Route service-manager and terminal-hangup signals into the interrupted-run path."""

from __future__ import annotations

import contextlib
import logging
import signal
import threading
from collections.abc import Iterator

SIGNALS = (signal.SIGTERM, signal.SIGHUP)


@contextlib.contextmanager
def terminate_as_interrupt() -> Iterator[None]:
    """Raise KeyboardInterrupt on the first SIGTERM or SIGHUP; ignore repeats.

    The interrupted path stops the container, harvests the login and writes the record, so a
    second signal (systemd resends none, but a shell may) must not abort that cleanup.
    Only the main thread can install handlers; elsewhere this is a no-op.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    received = []

    def interrupt(number, _frame):
        if received:
            logging.getLogger(__name__).warning(
                "signal %s ignored while the interrupted run is finalized", number
            )
            return
        received.append(number)
        raise KeyboardInterrupt(f"signal {number}")

    previous = {number: signal.signal(number, interrupt) for number in SIGNALS}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
