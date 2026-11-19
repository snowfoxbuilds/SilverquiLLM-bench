"""Cooldown Schedules: windows in which a Login Profile or a GPU Slot takes no new run.

A schedule is one small file (``cooldowns.json``) in the resource's own directory: a slot
directory beside its stored login, or a GPU Slot's directory under the state root. It holds
up to ``MAX_COOLDOWNS`` Cooldowns in ``SCHEDULE_LIMIT`` bytes, in force or still to come, which
may overlap. A Cooldown gates only the launch of a run; nothing here touches a stored login, a
runner's lock, or a run.

Readers never write: an ended Cooldown is simply ignored and dropped by the next write, and
an unreadable schedule is no Cooldown at all. Writers serialize on their own lock file, so
two operators' edits never lose each other's windows. A slot still holding the single
cooldown file from before schedules (``cooldown.json``) is read as one operator Cooldown
until the first write converts it (see ADR-024).
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .definition import KarnError, canonical, read_regular, strict_json
from .login import write_private

COOLDOWNS_FILE = "cooldowns.json"
LEGACY_COOLDOWN_FILE = "cooldown.json"
WRITE_LOCK = ".cooldowns.lock"
SCHEDULE_LIMIT = 64 * 1024
"""The most bytes a schedule file may hold: the reader reads no more, and no write makes more."""
LEGACY_LIMIT = 4096
MAX_COOLDOWNS = 256
MAX_NOTE = 200
HORIZON = timedelta(days=365)
"""No Cooldown may end more than this far ahead."""
STORED_HORIZON = HORIZON + timedelta(days=1)
"""A stored Cooldown ending more than this past the reader's now is malformed: no writer
makes one (a day's slack covers clocks a little apart), and its time may not even be
printable in local time."""
SCOPES = ("all", "fable")
SOURCES = ("operator", "usage-limit")
FABLE_MODEL_PREFIX = "claude-fable-"

_DURATION = re.compile(r"(?:(\d{1,6})d)?(?:(\d{1,6})h)?(?:(\d{1,6})m)?(?:(\d{1,6})s)?")
_CLOCK = r"([01]?\d|2[0-3]):([0-5]\d)"
_TIME = re.compile(_CLOCK)
_WEEKDAY_TIME = re.compile(r"([a-z]+)\s+" + _CLOCK)
_DATE_TIME = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ t]" + _CLOCK)
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def is_fable(model: str | None) -> bool:
    """Whether ``model`` spends the Fable limit, so a Fable-scoped Cooldown applies to it."""
    return isinstance(model, str) and model.startswith(FABLE_MODEL_PREFIX)


@dataclass(frozen=True)
class Cooldown:
    start: datetime
    end: datetime
    set_at: datetime
    scope: str = "all"
    source: str = "operator"
    note: str | None = None
    extend: bool = False
    """Whether the Cooldown is extended while its GPU Slot is used outside the bench (a GPU
    Slot's own; never a Login Profile's). An operator's edit clears it (see ``edited``)."""
    extensions: int = 0
    """How many ``EXTENSION_STEP`` steps its end has been moved on so far."""

    def in_force(self, now: datetime) -> bool:
        return self.start <= now < self.end

    def applies_to(self, model: str | None) -> bool:
        """Every Cooldown holds back a Fable run; one scoped to Fable holds back nothing else."""
        return self.scope == "all" or is_fable(model)

    def document(self) -> dict:
        document = {
            "start": _stamp(self.start),
            "end": _stamp(self.end),
            "set_at": _stamp(self.set_at),
            "scope": self.scope,
            "source": self.source,
        }
        if self.note is not None:
            document["note"] = self.note
        if self.extend:
            document["extend"] = True
        if self.extensions:
            document["extensions"] = self.extensions
        return document


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _instant(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("not a time")
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError("naive time")
    return moment.astimezone(UTC)


def _note(value: object) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_NOTE
        or any(not character.isprintable() for character in value)
    ):
        raise KarnError("invalid_cooldown_note")
    return value


def cooldown(
    start: datetime,
    end: datetime,
    *,
    now: datetime,
    scope: str = "all",
    source: str = "operator",
    note: str | None = None,
    extend: bool = False,
) -> Cooldown:
    """A new Cooldown, refused unless it ends after it starts, after now, and within a year."""
    if scope not in SCOPES:
        raise KarnError("invalid_cooldown_scope")
    if source not in SOURCES:
        raise KarnError("invalid_cooldown_source")
    if start.tzinfo is None or end.tzinfo is None:
        raise KarnError("invalid_cooldown_time")
    start, end = start.replace(microsecond=0), end.replace(microsecond=0)
    if end <= start or end <= now:
        raise KarnError("cooldown_ends_before_it_starts")
    if end - now > HORIZON:
        raise KarnError("cooldown_beyond_horizon")
    return Cooldown(
        start.astimezone(UTC),
        end.astimezone(UTC),
        now.astimezone(UTC).replace(microsecond=0),
        scope,
        source,
        _note(note),
        bool(extend),
    )


def edited(old: Cooldown, **fields) -> Cooldown:
    """``old`` as the operator changed it: an edited Cooldown is never extended again, so an
    end deliberately moved is not pushed back out by a busy GPU."""
    return replace(old, **fields, extend=False)


def _parsed(entry: object, now: datetime) -> Cooldown:
    if not isinstance(entry, dict) or not {"start", "end", "set_at", "scope", "source"} <= set(
        entry
    ):
        raise ValueError("not a cooldown")
    if entry["scope"] not in SCOPES or entry["source"] not in SOURCES:
        raise ValueError("unknown scope or source")
    start, end = _instant(entry["start"]), _instant(entry["end"])
    if end <= start:
        raise ValueError("empty window")
    if end - now > STORED_HORIZON:
        raise ValueError("beyond the horizon")
    extend, extensions = entry.get("extend", False), entry.get("extensions", 0)
    if type(extend) is not bool or type(extensions) is not int or not 0 <= extensions <= 10**6:
        raise ValueError("bad extension")
    return Cooldown(
        start,
        end,
        _instant(entry["set_at"]),
        entry["scope"],
        entry["source"],
        _note(entry.get("note")),
        extend,
        extensions,
    )


_UNREADABLE = (KarnError, OSError, KeyError, TypeError, ValueError, OverflowError, RecursionError)


def _present(path: Path) -> bool | None:
    """Whether a file is there; None when even that cannot be told."""
    try:
        return path.exists() or path.is_symlink()
    except OSError:
        return None


def _legacy(directory: Path, now: datetime) -> Cooldown | None:
    """The single cooldown from before schedules, as the operator Cooldown it always was."""
    path = directory / LEGACY_COOLDOWN_FILE
    if not _present(path):
        return None
    try:
        document = strict_json(read_regular(path, limit=LEGACY_LIMIT))
        end = _instant(document["until"])
    except _UNREADABLE:
        return None
    if end - now > STORED_HORIZON:
        return None
    try:
        set_at = _instant(document.get("set_at"))
    except _UNREADABLE:
        # The old reader held the slot until its end whatever ``set_at`` said.
        set_at = end - HORIZON
    # It held from whenever it was written; a ``set_at`` the clock has not reached yet must
    # not delay a hold the old reader kept in force.
    start = set_at if set_at <= datetime.now(UTC) else end - HORIZON
    return Cooldown(min(start, end - timedelta(seconds=1)), end, set_at, "all", "operator", None)


def _read(directory: Path, now: datetime) -> list[Cooldown]:
    """Every recorded Cooldown, ended ones included.

    A schedule that cannot be read, or holding a Cooldown that ends more than
    ``STORED_HORIZON`` past ``now``, is no Cooldown, never a refusal: it holds nothing back,
    and the next write replaces it. Only while no schedule exists does a ``cooldown.json``
    from before schedules count, so one a crashed conversion left behind is never revived.
    """
    path = directory / COOLDOWNS_FILE
    present = _present(path)
    if present is None:
        return []
    if not present:
        legacy = _legacy(directory, now)
        # A conversion finishing between the two looks has removed the old file; the
        # schedule it wrote holds the window now.
        if not _present(path):
            return [legacy] if legacy is not None else []
    try:
        document = strict_json(read_regular(path, limit=SCHEDULE_LIMIT))
        if not isinstance(document, dict) or document.get("format") != 1:
            raise ValueError("unknown format")
        entries = document["cooldowns"]
        if not isinstance(entries, list) or len(entries) > MAX_COOLDOWNS:
            raise ValueError("not a list")
        return [_parsed(entry, now) for entry in entries]
    except _UNREADABLE:
        return []


def read_schedule(directory: Path, *, now: datetime | None = None) -> list[Cooldown]:
    """The Cooldowns not yet ended at ``now``, soonest first."""
    now = now or datetime.now(UTC)
    return sorted(
        (c for c in _read(Path(directory), now) if c.end > now), key=lambda c: (c.start, c.end)
    )


def in_force(
    directory: Path, *, model: str | None = None, now: datetime | None = None
) -> list[Cooldown]:
    """The Cooldowns in force at ``now`` that hold back a run of ``model``; with no model
    known, those that hold back every run."""
    now = now or datetime.now(UTC)
    return [c for c in read_schedule(directory, now=now) if c.in_force(now) and c.applies_to(model)]


def held_until(
    directory: Path, *, model: str | None = None, now: datetime | None = None
) -> datetime | None:
    """When the last Cooldown in force for ``model`` ends; None when none holds it back."""
    return max((c.end for c in in_force(directory, model=model, now=now)), default=None)


@contextlib.contextmanager
def _writing(directory: Path, wait: float | None) -> Iterator[None]:
    """Hold the schedule's write lock; with ``wait`` seconds given, refuse once they pass."""
    descriptor = os.open(
        directory / WRITE_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600
    )
    try:
        if wait is None:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        else:
            deadline = time.monotonic() + wait
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise KarnError("cooldown_schedule_busy") from None
                    time.sleep(0.05)
        yield
    finally:
        os.close(descriptor)


def edit_schedule(
    directory: Path,
    change: Callable[[list[Cooldown]], list[Cooldown]],
    *,
    now: datetime,
    wait: float | None = None,
    ended: bool = False,
) -> list[Cooldown]:
    """Apply ``change`` to the Cooldowns not yet ended, or with ``ended`` to every recorded
    one, and write the result atomically; ended Cooldowns are never written back.

    The written schedule supersedes a ``cooldown.json`` from before schedules, which this
    removes only after the schedule holding its window is durably in place, so a crash in
    between keeps the hold. With ``wait`` given, another writer holding the schedule longer
    than that many seconds refuses the edit as busy instead of blocking.

    A result of more than ``MAX_COOLDOWNS`` Cooldowns or ``SCHEDULE_LIMIT`` bytes is refused
    as ``cooldown_schedule_full`` before anything is written, since the reader would take
    the file for no Cooldown at all. Ended Cooldowns are dropped first, so they take no room.
    """
    directory = Path(directory)
    with _writing(directory, wait):
        current = [c for c in _read(directory, now) if ended or c.end > now]
        kept = sorted((c for c in change(current) if c.end > now), key=lambda c: (c.start, c.end))
        written = canonical({"format": 1, "cooldowns": [c.document() for c in kept]})
        if len(kept) > MAX_COOLDOWNS or len(written) > SCHEDULE_LIMIT:
            raise KarnError("cooldown_schedule_full")
        write_private(directory / COOLDOWNS_FILE, written)
        (directory / LEGACY_COOLDOWN_FILE).unlink(missing_ok=True)
    return kept


def add_cooldown(directory: Path, new: Cooldown, *, now: datetime) -> Cooldown:
    """Add one Cooldown beside those already scheduled."""
    edit_schedule(directory, lambda cooldowns: [*cooldowns, new], now=now)
    return new


def remove_cooldown(directory: Path, old: Cooldown, *, now: datetime) -> bool:
    """Remove one Cooldown, matched exactly; returns whether it was there."""
    found = []

    def without(cooldowns: list[Cooldown]) -> list[Cooldown]:
        found.extend(c for c in cooldowns if c == old)
        return [c for c in cooldowns if c != old]

    edit_schedule(directory, without, now=now)
    return bool(found)


def clear_schedule(directory: Path, *, now: datetime) -> int:
    """Remove every Cooldown, in force or to come; returns how many there were."""
    count = []

    def nothing(cooldowns: list[Cooldown]) -> list[Cooldown]:
        count.append(len(cooldowns))
        return []

    edit_schedule(directory, nothing, now=now)
    return count[0]


def extend_hold(
    directory: Path, by: timedelta, *, now: datetime, wait: float | None = None
) -> Cooldown:
    """Hold the resource ``by`` longer, returning the Cooldown that now holds it.

    The in-force Cooldown that ends last, whatever its scope, ends ``by`` later and keeps
    everything else of it; with none in force, a new operator Cooldown on every run runs
    from now. Cooldowns still to come are left alone.
    """
    held = []

    def longer(cooldowns: list[Cooldown]) -> list[Cooldown]:
        in_force = [c for c in cooldowns if c.in_force(now)]
        if not in_force:
            held.append(cooldown(now, now + by, now=now))
            return [*cooldowns, held[0]]
        last = max(in_force, key=lambda c: c.end)
        if last.end + by - now > HORIZON:
            raise KarnError("cooldown_beyond_horizon")
        held.append(replace(last, end=last.end + by))
        return [held[0] if c is last else c for c in cooldowns]

    edit_schedule(directory, longer, now=now, wait=wait)
    return held[0]


def end_in_force_after(
    directory: Path, grace: timedelta, *, now: datetime, wait: float | None = None
) -> datetime | None:
    """End every Cooldown in force ``grace`` from now, leaving those still to come alone;
    None, writing nothing, when none is in force."""
    directory = Path(directory)
    if not any(c.in_force(now) for c in read_schedule(directory, now=now)):
        return None
    until = (now + grace).replace(microsecond=0)

    def sooner(cooldowns: list[Cooldown]) -> list[Cooldown]:
        return [
            replace(c, end=until) if c.in_force(now) and c.end > until else c for c in cooldowns
        ]

    edit_schedule(directory, sooner, now=now, wait=wait)
    return until


EXTENSION_STEP = timedelta(minutes=30)
EXTENSION_LOOKAHEAD = timedelta(minutes=1)
"""How soon before its end a Cooldown counts as ending, so a check every scheduler pass
extends it before the resource is ever free."""


def _ending(cooldowns: list[Cooldown], now: datetime) -> Cooldown | None:
    """The extendable Cooldown whose end frees the resource: begun, ending within
    ``EXTENSION_LOOKAHEAD`` or ended less than ``EXTENSION_STEP`` ago, with no other Cooldown
    covering its end or begun since; the one ending last.

    A Cooldown ended longer ago stays ended, so a first check more than a step late never
    extends it: the trade-off is safe because a claim already passes over a GPU Slot whose
    GPUs are busy, and a window ended long ago is never revived by work that starts later."""
    candidates = [
        c
        for c in cooldowns
        if c.extend
        and c.start <= now
        and now - EXTENSION_STEP < c.end <= now + EXTENSION_LOOKAHEAD
        and not any(o is not c and o.start <= c.end < o.end for o in cooldowns)
        and not any(c.end < o.start <= now for o in cooldowns)
    ]
    return max(candidates, key=lambda c: c.end, default=None)


def ending_cooldown(directory: Path, *, now: datetime) -> Cooldown | None:
    """The Cooldown of ``directory`` that is ending and would be extended while in use."""
    return _ending(_read(Path(directory), now), now)


def drop_ended(directory: Path, *, now: datetime, wait: float | None = None) -> None:
    """Write the schedule back without its ended Cooldowns, so one that lapsed stays lapsed."""
    edit_schedule(directory, lambda cooldowns: cooldowns, now=now, wait=wait)


def extended(cooldowns: list[Cooldown], now: datetime) -> list[Cooldown] | None:
    """The schedule with its ending Cooldown extended, or None when none is due.

    Its end moves on one ``EXTENSION_STEP`` from where it was, which is after now since only a
    Cooldown ended less than a step ago is due, so the result does not depend on when the
    check ran. An end that reaches the start of a later Cooldown merges the two: one window
    from the first's start to the later end, keeping the later Cooldown's note and whether
    it extends."""
    ending = _ending(cooldowns, now)
    if ending is None:
        return None
    end = ending.end + EXTENSION_STEP
    if end - now > HORIZON:
        return None
    reached = [o for o in cooldowns if o is not ending and ending.end <= o.start <= end]
    if reached:
        later = max(reached, key=lambda o: o.end)
        merged = replace(
            later,
            start=ending.start,
            end=max(end, later.end),
            extensions=ending.extensions + later.extensions + 1,
        )
    else:
        merged = replace(ending, end=end, extensions=ending.extensions + 1)
    gone = {id(ending), *map(id, reached)}
    return [*(c for c in cooldowns if id(c) not in gone), merged]


class _Unchanged(Exception):
    pass


def extend_ending(directory: Path, *, now: datetime, wait: float | None) -> Cooldown | None:
    """Extend the Cooldown that is ending, as ``extended`` does, and return the Cooldown that
    now holds the resource; None, writing nothing, when none is due."""
    result = []

    def extend(cooldowns: list[Cooldown]) -> list[Cooldown]:
        changed = extended(cooldowns, now)
        if changed is None:
            raise _Unchanged
        result.append(changed[-1])
        return changed

    try:
        edit_schedule(directory, extend, now=now, wait=wait, ended=True)
    except _Unchanged:
        return None
    return result[0]


def parse_duration(text: str) -> timedelta:
    """A positive span such as ``30m``, ``5h``, ``2d`` or ``1h30m``, at most a year."""
    match = _DURATION.fullmatch(text.strip().lower())
    if not text.strip() or match is None or not any(match.groups()):
        raise KarnError("invalid_cooldown_duration")
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    span = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if span <= timedelta(0) or span > HORIZON:
        raise KarnError("invalid_cooldown_duration")
    return span


def _aware(naive: datetime, tz, fold: int) -> datetime:
    # With no zone given, the host's own rules (the C library's, from TZ or /etc/localtime)
    # place the wall time on its own date, its DST changes included.
    naive = naive.replace(fold=fold)
    return naive.replace(tzinfo=tz) if tz is not None else naive.astimezone()


def _occurrences(naive: datetime, tz) -> list[datetime]:
    """The moments a wall time names, in UTC and soonest first: both of an hour the clocks
    repeat, and for an hour they skip, the reading from before the change."""
    readings = [_aware(naive, tz, fold).astimezone(UTC) for fold in (0, 1)]
    real = [m for m in readings if m.astimezone(tz).replace(tzinfo=None) == naive]
    return sorted(real or readings[:1])


def _next(naives, tz, now: datetime) -> datetime | None:
    """The first occurrence strictly after ``now`` of the first wall time that has one."""
    return next((m for naive in naives for m in _occurrences(naive, tz) if m > now), None)


def parse_time(text: str, *, now: datetime, base: datetime | None = None, tz=None) -> datetime:
    """A moment the operator typed, in the host's local time (or ``tz``), as a UTC time.

    ``14:00`` is its next occurrence strictly after now, either reading of an hour the
    clocks repeat included; ``Fri 09:00`` the next Friday at 09:00, and ``2026-11-20 09:00``
    that day; an offset such as ``+3h`` or ``1d`` counts from ``base``, which is now unless
    given (an end counts from its start). A moment more than ``HORIZON`` ahead is refused,
    as no Cooldown may reach it, and so is one no calendar can hold.
    """
    try:
        moment = _parse_time(text, now=now, base=base, tz=tz)
    except (ValueError, OverflowError):
        raise KarnError("invalid_cooldown_time") from None
    if moment - now > HORIZON:
        raise KarnError("cooldown_beyond_horizon")
    return moment


def _parse_time(text: str, *, now: datetime, base: datetime | None, tz) -> datetime:
    words = " ".join(text.strip().lower().split())
    offset = words.removeprefix("+")
    if _DURATION.fullmatch(offset) and any(_DURATION.fullmatch(offset).groups()):
        return ((base or now) + parse_duration(offset)).astimezone(UTC)
    today = now.astimezone(tz).replace(tzinfo=None, second=0, microsecond=0)
    if match := _TIME.fullmatch(words):
        start = today.replace(hour=int(match[1]), minute=int(match[2]))
        moment = _next((start + timedelta(days=ahead) for ahead in range(2)), tz, now)
        if moment is not None:
            return moment
    if (match := _WEEKDAY_TIME.fullmatch(words)) and any(
        match[1] in (name, name[:3]) for name in _WEEKDAYS
    ):
        day = next(i for i, name in enumerate(_WEEKDAYS) if match[1] in (name, name[:3]))
        start = today.replace(hour=int(match[2]), minute=int(match[3]))
        candidates = (start + timedelta(days=ahead) for ahead in range(8))
        moment = _next((c for c in candidates if c.weekday() == day), tz, now)
        if moment is not None:
            return moment
    if match := _DATE_TIME.fullmatch(words):
        year, month, day, hour, minute = (int(part) for part in match.groups())
        naive = today.replace(year=year, month=month, day=day, hour=hour, minute=minute)
        return _next([naive], tz, now) or _occurrences(naive, tz)[0]
    raise KarnError("invalid_cooldown_time")
