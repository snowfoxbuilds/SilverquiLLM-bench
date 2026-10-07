"""A live run's provisional Estimated Cost from its telemetry events (RUN-MONITORING.md, Dashboard).

Codex request events are priced with the bench's price table, as the end of a run prices
them when native journals are missing. Claude's events lack the cache-write duration
split the table needs, so a Claude run sums Claude Code's own per-request ``cost_usd``.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from silverquillm.karn.observations import _OTLP_TOKENS
from silverquillm.karn.pricing import price_requests

from ._read import MAX_USD

EVENTS_FILE = "observations.events.jsonl"
# Read at most this much per update; a backlog is consumed over successive polls.
MAX_READ = 16 * 1024 * 1024
MAX_LINE = 1024 * 1024
CLAUDE_TOKENS = {
    "input_tokens": "input_tokens",
    "cached_input_tokens": "cache_read_tokens",
    "cache_write_input_tokens": "cache_creation_tokens",
    "output_tokens": "output_tokens",
}


@dataclass(frozen=True)
class RequestCost:
    timestamp_ms: int
    model: str | None
    tokens: dict[str, int | None]
    usd: Decimal | None


def _count(value: Any) -> int | None:
    # ``isdigit`` alone admits digits ``int`` refuses, such as superscripts.
    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 20:
        return int(value)
    return value if type(value) is int and value >= 0 else None


def _usd(value: Any) -> Decimal | None:
    if not isinstance(value, str | int | float) or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() and 0 <= number <= MAX_USD else None


def _stamp(event: dict) -> int:
    stamp = event.get("timestamp_ms")
    return stamp if type(stamp) is int and stamp > 0 else 0


@dataclass
class ProvisionalCost:
    """Follows one run's events file; call ``update`` on each poll, then read the totals."""

    run_dir: Path
    adapter: str | None
    _offset: int = 0
    _partial: bytes = b""
    _seen: set = field(default_factory=set)
    _codex: list = field(default_factory=list)
    _claude: list = field(default_factory=list)
    _priced: list = field(default_factory=list)
    available: bool = False

    def update(self) -> None:
        path = self.run_dir / EVENTS_FILE
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            return
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                return
            self.available = True
            if info.st_size < self._offset:
                self._reset()  # The file was replaced; read it from the start.
            os.lseek(descriptor, self._offset, os.SEEK_SET)
            chunk = os.read(descriptor, MAX_READ)
        finally:
            os.close(descriptor)
        self._offset += len(chunk)
        lines = (self._partial + chunk).split(b"\n")
        self._partial = lines.pop()
        if len(self._partial) > MAX_LINE:
            self._partial = b""  # an overlong line is never a request event
        changed = False
        for line in lines:
            if len(line) > MAX_LINE:
                continue
            try:
                event = json.loads(line)
            except (ValueError, RecursionError):
                continue
            if isinstance(event, dict) and self._ingest(event):
                changed = True
        if changed and self._codex:
            self._priced = price_requests(self._codex)

    def _reset(self) -> None:
        self._offset, self._partial = 0, b""
        self._seen, self._codex, self._claude, self._priced = set(), [], [], []

    def _ingest(self, event: dict) -> bool:
        attributes = event.get("attributes")
        identity = event.get("id")
        if (
            not isinstance(attributes, dict)
            or not isinstance(identity, str)
            or identity in self._seen
        ):
            return False
        kind = event.get("kind")
        if kind == "claude_code.api_request":
            self._seen.add(identity)
            self._claude.append(
                RequestCost(
                    _stamp(event),
                    attributes.get("model") if isinstance(attributes.get("model"), str) else None,
                    {key: _count(attributes.get(source)) for key, source in CLAUDE_TOKENS.items()},
                    _usd(attributes.get("cost_usd")),
                )
            )
            return True
        if (
            kind in ("codex.sse_event", "codex.websocket_event")
            and attributes.get("event.kind") == "response.completed"
            and "input_token_count" in attributes
        ):
            self._seen.add(identity)
            thread, model = event.get("thread_id"), attributes.get("model")
            # The price table keys on both, so neither may be an unhashable JSON value.
            self._codex.append(
                {
                    "response_id": identity,
                    "thread_id": thread if isinstance(thread, str) else "",
                    "model": model if isinstance(model, str) else None,
                    "timestamp_ms": _stamp(event),
                    "usage": {
                        key: _count(attributes.get(source)) for key, source in _OTLP_TOKENS.items()
                    },
                }
            )
            return True
        return False

    @property
    def requests(self) -> list[RequestCost]:
        if self._claude:
            return list(self._claude)
        return [
            RequestCost(
                request["timestamp_ms"],
                request["model"],
                request["usage"],
                _usd(price["usd"]),
            )
            for request, price in zip(self._codex, self._priced, strict=False)
        ]

    @property
    def total(self) -> Decimal | None:
        """The sum of priced requests; None until the events file exists."""
        if not self.available:
            return None
        return sum((row.usd for row in self.requests if row.usd is not None), Decimal(0))

    @property
    def unpriced(self) -> int:
        return sum(1 for row in self.requests if row.usd is None)
