"""The newest subscription usage reading a run observed for its Login Profile.

Claude Code reports the account's weekly window in ``rate_limit_event`` lines on its
stream-json stdout; Codex reports it in the ``rate_limits`` of its session rollouts, which
sit in the login plugin's work directory beside live credentials. Only the reading's
allowlisted fields are kept, never a whole line, and only rollout files are opened there.
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from silverquillm.safe_files import iter_regular_files, open_directory

from .definition import KarnError, read_regular

WEEK_MINUTES = 7 * 24 * 60
MAX_PERCENT = 1000.0
MAX_STDOUT_BYTES = 256 * 1024 * 1024
MAX_SESSION_BYTES = 128 * 1024 * 1024
MAX_SESSION_FILES = 10_000
# A real reading line is a few kilobytes.
MAX_LINE_BYTES = 1024 * 1024
# Reset times outside this range are malformed rather than a real window boundary.
EARLIEST_RESET = datetime(2000, 1, 1, tzinfo=UTC).timestamp()
LATEST_RESET = datetime(2100, 1, 1, tzinfo=UTC).timestamp()
PROVIDERS = {"karn-codex-login": "codex", "karn-claude-login": "claude"}


def missing(*reasons: str) -> dict[str, Any]:
    return {"completeness": "missing", "reasons": sorted(set(reasons)), "value": None}


def _complete(value: dict[str, Any], reasons: set[str]) -> dict[str, Any]:
    return {"completeness": "complete", "reasons": sorted(reasons), "value": value}


def provider_for(login: str | None, adapter: str | None) -> str | None:
    """A Login Profile is ``<plugin-id>/<slot>``; older runs named only the slot."""
    if not login:
        return None
    plugin = login.split("/", 1)[0] if "/" in login else None
    if plugin in PROVIDERS:
        return PROVIDERS[plugin]
    return adapter if adapter in PROVIDERS.values() else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _instant(epoch_seconds: Any) -> str | None:
    seconds = _number(epoch_seconds)
    if seconds is None or not EARLIEST_RESET <= seconds < LATEST_RESET:
        return None
    return datetime.fromtimestamp(int(seconds), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            return None
        return _instant(moment.timestamp())
    except (ValueError, OverflowError):
        return None


def _reading(provider, percent, window, resets_at, observed_at) -> dict[str, Any] | None:
    if percent is None or not 0 <= percent <= MAX_PERCENT or resets_at is None:
        return None
    return {
        "provider": provider,
        "utilization_percent": round(percent, 4) + 0.0,  # never -0.0
        "window_minutes": window,
        "resets_at": resets_at,
        "observed_at": observed_at,
    }


def claude_reading(document: Any) -> dict[str, Any] | None:
    """The seven-day window of one ``rate_limit_event``, whose utilization is a fraction."""
    try:
        window = document["rate_limit_info"]["unifiedWindows"]["seven_day"]
        fraction, resets_at = window["utilization"], window["resetsAt"]
    except (KeyError, TypeError):
        return None
    fraction = _number(fraction)
    percent = None if fraction is None else fraction * 100
    # The stream carries no time of its own; the run's container stop bounds it.
    return _reading("claude", percent, WEEK_MINUTES, _instant(resets_at), None)


def codex_reading(document: Any) -> tuple[dict[str, Any] | None, str | None]:
    """The weekly window of one rollout ``rate_limits``, or why the line has none.

    Codex names its windows primary and secondary; the weekly one is chosen by its length.
    """
    payload = document.get("payload") if isinstance(document, dict) else None
    limits = payload.get("rate_limits") if isinstance(payload, dict) else None
    if limits is None:
        return None, None if isinstance(document, dict) else "malformed_reading_dropped"
    if not isinstance(limits, dict):
        return None, "malformed_reading_dropped"
    for window in (limits.get("primary"), limits.get("secondary")):
        if not isinstance(window, dict):
            continue
        minutes = window.get("window_minutes")
        if isinstance(minutes, bool) or minutes != WEEK_MINUTES:
            continue
        reading = _reading(
            "codex",
            _number(window.get("used_percent")),
            WEEK_MINUTES,
            _instant(window.get("resets_at")),
            _timestamp(document.get("timestamp")),
        )
        return reading, None if reading else "malformed_reading_dropped"
    return None, "codex_weekly_window_absent"


def _documents(content: bytes, marker: bytes):
    """Parse only the bounded lines that can hold a reading; any other line is never decoded.

    Lines are located around each marker rather than split out, and an overlong line is
    dropped unparsed: the container can write either, and both would cost the host far
    more memory than the bytes it read.
    """
    position = content.find(marker)
    while position != -1:
        start = content.rfind(b"\n", 0, position) + 1
        end = content.find(b"\n", position)
        end = len(content) if end == -1 else end
        if end - start > MAX_LINE_BYTES:
            yield None
        else:
            try:
                yield json.loads(content[start:end])
            except (ValueError, RecursionError):
                yield None
        position = content.find(marker, end)


def claude_usage(stdout: Path) -> dict[str, Any]:
    try:
        content = read_regular(stdout, limit=MAX_STDOUT_BYTES)
    except KarnError:
        return missing("claude_stdout_unavailable")
    newest, reasons = None, set()
    for document in _documents(content, b'"rate_limit_event"'):
        if document is None:
            reasons.add("malformed_reading_dropped")
            continue
        if not isinstance(document, dict) or document.get("type") != "rate_limit_event":
            continue
        reading = claude_reading(document)
        if reading is None:
            reasons.add("malformed_reading_dropped")
        else:
            newest = reading
    if newest is None:
        return missing("claude_rate_limit_event_absent", *reasons)
    return _complete(newest, reasons)


def _is_rollout(path: PurePosixPath) -> bool:
    return path.name.startswith("rollout-") and path.name.endswith(".jsonl")


def codex_usage(native: Path) -> dict[str, Any]:
    """Read ``native/sessions`` rollouts only; nothing else in the directory is opened."""
    try:
        descriptor = open_directory(Path(native), ("sessions",))
    except OSError:
        return missing("codex_sessions_unavailable")
    newest, reasons, order = None, set(), 0
    try:
        for _, content in iter_regular_files(
            descriptor,
            accept=_is_rollout,
            max_files=MAX_SESSION_FILES,
            max_bytes=MAX_SESSION_BYTES,
        ):
            for document in _documents(content, b'"rate_limits"'):
                order += 1
                reading, problem = codex_reading(document)
                if problem is not None:
                    reasons.add(problem)
                if reading is not None:
                    key = (reading["observed_at"] or "", order)
                    if newest is None or key > newest[0]:
                        newest = (key, reading)
    except OSError:
        reasons.add("codex_sessions_partially_read")
    finally:
        os.close(descriptor)
    if newest is None:
        return missing("codex_rate_limits_absent", *reasons)
    return _complete(newest[1], reasons)


def subscription_usage(
    provider: str | None, *, codex: dict[str, Any] | None, stdout: Path
) -> dict[str, Any]:
    """The record's ``subscription_usage`` measurement for a run's Login Profile provider."""
    if provider == "claude":
        return claude_usage(stdout)
    if provider == "codex":
        return codex if codex is not None else missing("codex_sessions_unavailable")
    return missing("no_login_profile")
