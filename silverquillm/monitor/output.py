"""A run's output for human eyes: live Docker logs, retained logs, and live usage readings.

Live Docker logs are unredacted, so every line is redacted with its login's secrets before
anything keeps it (RUN-MONITORING.md, Run details view). Retained ``host/*.log`` files were
redacted when they were captured.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import threading
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from silverquillm.karn.definition import KarnError, read_regular, strict_json
from silverquillm.karn.login import LOGIN_PLUGINS, secret_values
from silverquillm.karn.login_pool import SECRET_FILE_LIMIT, SLOT_NAME, logins_root
from silverquillm.karn.subscription_usage import claude_reading, codex_usage

from ._read import instant
from .history import UsageReading

REDACTED = b"[REDACTED]"
# A displayed line keeps its first 16 KiB; with DEFAULT_KEEP lines a followed run holds ~32 MiB.
MAX_LINE = 16 * 1024
TRUNCATED = b" [truncated]"
READ_CHUNK = 65536
DEFAULT_TAIL = 2000
DEFAULT_KEEP = 2000
MAX_RETAINED_READ = 8 * 1024 * 1024
STREAMS = ("stdout", "stderr")
# ``docker logs --timestamps`` stamps every message in Go's RFC3339NanoFixed, and Docker
# splits a line longer than its log buffer (16 KiB for json-file) into partial messages,
# each stamped anew: a secret across a split would never match its redaction.
DOCKER_STAMP = re.compile(rb"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{9}(?:Z|[+-]\d\d:\d\d) ")
DOCKER_STAMP_MAX = 36


def profile_redactions(state_root: Path | None, login: str | None) -> frozenset[bytes]:
    """The values the login plugin redacts for this Login Profile: its stored login's leaves.

    The stored login is read only to learn what to hide; nothing derived from it is shown.
    """
    if state_root is None or not login:
        return frozenset()
    plugin, _, slot = login.partition("/")
    if plugin not in LOGIN_PLUGINS or not SLOT_NAME.fullmatch(slot):
        return frozenset()
    path = logins_root(Path(state_root)) / plugin / slot / "secret.json"
    try:
        document = strict_json(read_regular(path, limit=SECRET_FILE_LIMIT))
    except (KarnError, OSError):
        return frozenset()
    return frozenset(secret_values(document)) if isinstance(document, str) else frozenset()


def redact(data: bytes, redactions: Iterable[bytes]) -> bytes:
    for secret in sorted(redactions, key=len, reverse=True):
        data = data.replace(secret, REDACTED)
    return data


def redacted_head(data: bytes, limit: int, redactions: Iterable[bytes]) -> bytes:
    """At most ``limit`` source bytes, redacted, never ending inside a secret.

    A cut through a secret would show its prefix unredacted, so the cut moves before it.
    """
    redactions = tuple(redactions)
    cut, moved = min(limit, len(data)), True
    while moved:
        moved = False
        for secret in redactions:
            start = data.find(secret, max(0, cut - len(secret) + 1))
            while start != -1 and start < cut:
                if start + len(secret) > cut:
                    cut, moved = start, True
                    break
                start = data.find(secret, start + 1)
    return redact(data[:cut], redactions)


@dataclass(frozen=True)
class LogLine:
    seq: int
    stream: str
    text: str
    at: datetime | None
    truncated: bool = False


def split_timestamp(line: bytes) -> tuple[datetime | None, bytes]:
    """``docker logs --timestamps`` prefixes each line with its RFC 3339 time and a space."""
    stamp, separator, rest = line.partition(b" ")
    if separator and len(stamp) <= 40:
        moment = instant(stamp.decode(errors="replace"))
        if moment is not None:
            return moment, rest
    return None, line


def join_partials(line: bytes) -> bytes:
    """A followed line as the container wrote it, behind its own leading stamp only."""
    first = DOCKER_STAMP.match(line)
    start = first.end() if first else 0
    return line[:start] + DOCKER_STAMP.sub(b"", line[start:])


def claude_line_reading(line: bytes, at: datetime | None) -> UsageReading | None:
    """A ``rate_limit_event`` line's weekly window, observed when Docker logged the line."""
    if b'"rate_limit_event"' not in line or len(line) > MAX_LINE:
        return None
    try:
        document = json.loads(line)
    except (ValueError, RecursionError):
        return None
    if not isinstance(document, dict) or document.get("type") != "rate_limit_event":
        return None
    value = claude_reading(document)
    resets_at = instant(value.get("resets_at")) if value else None
    if value is None or resets_at is None:
        return None
    return UsageReading(
        "claude", value["utilization_percent"], value["window_minutes"], resets_at, at
    )


class LineSplitter:
    """Bytes in, redacted bounded lines out; an overlong line keeps only its redacted head."""

    def __init__(
        self,
        redactions: Iterable[bytes],
        limit: int = MAX_LINE,
        *,
        join: Callable[[bytes], bytes] | None = None,
    ):
        self.redactions = tuple(redactions)
        self.margin = max((len(secret) for secret in self.redactions), default=0)
        self.limit = limit
        self.join = join
        # An unfinished stamp at the buffer's end is not joined yet; it must lie past any
        # secret that crosses the cut.
        self.slack = DOCKER_STAMP_MAX if join else 0
        self.buffer = b""
        self.discarding = False

    def feed(self, chunk: bytes) -> list[tuple[bytes, bytes, bool]]:
        """``(raw, redacted, truncated)`` per completed line; ``raw`` is only for readings."""
        out = []
        self.buffer += chunk
        while True:
            end = self.buffer.find(b"\n")
            if end == -1:
                if self.join:
                    # Joined as it grows, so a line of stamps alone cannot grow it unbounded.
                    self.buffer = self.join(self.buffer)
                if len(self.buffer) > self.limit + self.margin + self.slack:
                    if not self.discarding:
                        out.append(
                            (b"", redacted_head(self.buffer, self.limit, self.redactions), True)
                        )
                    self.discarding = True
                    # Keep a secret's length, so the rest of the line is still recognized as it.
                    self.buffer = self.buffer[-self.margin :] if self.margin else b""
                return out
            line, self.buffer = self.buffer[:end].rstrip(b"\r"), self.buffer[end + 1 :]
            if self.join:
                line = self.join(line)
            if self.discarding:
                self.discarding = False
                continue
            if len(line) > self.limit:
                out.append((b"", redacted_head(line, self.limit, self.redactions), True))
            else:
                out.append((line, redact(line, self.redactions), False))

    def flush(self) -> list[tuple[bytes, bytes, bool]]:
        rest = self.feed(b"\n") if self.buffer else []
        self.buffer = b""
        return rest


Popen = Callable[..., subprocess.Popen]


class LogFollower:
    """Follows ``docker logs`` of one run container in background threads.

    ``lines_since`` returns the redacted lines after a sequence number, so a view can poll
    for what is new; the newest Claude usage reading seen on stdout is kept as well.
    """

    def __init__(
        self,
        container: str,
        redactions: Iterable[bytes],
        *,
        tail: int = DEFAULT_TAIL,
        keep: int = DEFAULT_KEEP,
        popen: Popen = subprocess.Popen,
    ):
        self.container = container
        self.redactions = frozenset(redactions)
        self.tail, self.keep, self.popen = tail, keep, popen
        self._lines: deque[LogLine] = deque(maxlen=keep)
        self._seq = 0
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._threads: list[threading.Thread] = []
        self.reading: UsageReading | None = None
        self.error: str | None = None

    def start(self) -> None:
        try:
            self._process = self.popen(
                [
                    "docker",
                    "logs",
                    "--follow",
                    "--timestamps",
                    "--tail",
                    str(self.tail),
                    self.container,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError:
            self.error = "docker_unavailable"
            return
        for name, stream in (("stdout", self._process.stdout), ("stderr", self._process.stderr)):
            thread = threading.Thread(target=self._pump, args=(name, stream), daemon=True)
            thread.start()
            self._threads.append(thread)

    def _pump(self, name: str, stream) -> None:
        splitter = LineSplitter(self.redactions, MAX_LINE + 64, join=join_partials)
        try:
            while chunk := stream.read1(READ_CHUNK):
                self._accept(name, splitter.feed(chunk))
            self._accept(name, splitter.flush())
        except (OSError, ValueError):
            pass
        finally:
            stream.close()

    def _accept(self, name: str, rows) -> None:
        for raw, redacted, truncated in rows:
            at, text = split_timestamp(redacted)
            if name == "stdout" and raw:
                reading = claude_line_reading(split_timestamp(raw)[1], at)
                if reading is not None:
                    self.reading = reading
            with self._lock:
                self._seq += 1
                self._lines.append(
                    LogLine(self._seq, name, text.decode(errors="replace"), at, truncated)
                )

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def lines_since(self, seq: int = 0, stream: str | None = None) -> list[LogLine]:
        with self._lock:
            return [
                line
                for line in self._lines
                if line.seq > seq and (stream is None or line.stream == stream)
            ]

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        for thread in self._threads:
            thread.join(timeout=5)


def retained_lines(
    run_dir: Path, stream: str, *, max_bytes: int = MAX_RETAINED_READ
) -> list[LogLine]:
    """The tail of a stopped run's retained ``host/<stream>.log``, already redacted at capture."""
    if stream not in STREAMS:
        raise ValueError(stream)
    path = Path(run_dir) / "host" / (stream + ".log")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return []
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            return []  # a FIFO would block the view, a directory fail its read
        start = max(0, info.st_size - max_bytes)
        os.lseek(descriptor, start, os.SEEK_SET)
        data = os.read(descriptor, max_bytes)
    except OSError:
        return []
    finally:
        os.close(descriptor)
    if start:
        data = data.partition(b"\n")[2]  # the first line was cut by the window
    splitter = LineSplitter((), MAX_LINE)
    rows = splitter.feed(data) + splitter.flush()
    return [
        LogLine(index, stream, redacted.decode(errors="replace"), None, truncated)
        for index, (_, redacted, truncated) in enumerate(rows, 1)
    ]


def live_codex_reading(state_root: Path | None, login: str | None) -> UsageReading | None:
    """The newest weekly reading in a busy Codex Login Profile's live rollouts.

    Only rollout files are opened, and only their allowlisted ``rate_limits`` fields are kept.
    """
    if state_root is None or not login:
        return None
    plugin, _, slot = login.partition("/")
    if plugin != "karn-codex-login" or not SLOT_NAME.fullmatch(slot):
        return None
    usage = codex_usage(logins_root(Path(state_root)) / plugin / slot / "plugin" / "work")
    value = usage.get("value")
    if not isinstance(value, dict):
        return None
    resets_at = instant(value.get("resets_at"))
    if resets_at is None:
        return None
    return UsageReading(
        "codex",
        value["utilization_percent"],
        value["window_minutes"],
        resets_at,
        instant(value.get("observed_at")),
    )
