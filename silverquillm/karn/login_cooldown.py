"""Login Cooldowns: an operator's hold that keeps a Login Profile out of new runs until a time.

A cooldown is one small file beside a slot's stored login. Only ``silverquillm login
cooldown`` writes it; pool acquisition and the monitor only read it, and an expired or
unreadable one is simply no cooldown, so nothing ever has to clean it up.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .definition import KarnError, canonical, read_regular, strict_json
from .login import write_private

COOLDOWN_FILE = "cooldown.json"
COOLDOWN_LIMIT = 4096
MAX_COOLDOWN = timedelta(days=365)
_DURATION = re.compile(r"(?:(\d{1,6})d)?(?:(\d{1,6})h)?(?:(\d{1,6})m)?(?:(\d{1,6})s)?")


def parse_duration(text: str) -> timedelta:
    """A positive span such as ``30m``, ``5h``, ``2d`` or ``1h30m``, at most a year."""
    match = _DURATION.fullmatch(text.strip().lower())
    if not text.strip() or match is None or not any(match.groups()):
        raise KarnError("invalid_cooldown_duration")
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    span = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if span <= timedelta(0) or span > MAX_COOLDOWN:
        raise KarnError("invalid_cooldown_duration")
    return span


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def set_cooldown(directory: Path, until: datetime, *, now: datetime) -> None:
    """Hold the slot in ``directory`` until ``until``; its login and lock are never touched."""
    document = {"format": 1, "set_at": _stamp(now), "until": _stamp(until)}
    write_private(Path(directory) / COOLDOWN_FILE, canonical(document))


def clear_cooldown(directory: Path) -> bool:
    """Lift the slot's cooldown; returns whether one was there."""
    try:
        (Path(directory) / COOLDOWN_FILE).unlink()
    except FileNotFoundError:
        return False
    return True


def cooldown_until(directory: Path, *, now: datetime | None = None) -> datetime | None:
    """When the slot's cooldown ends, or None when it has none in force at ``now``."""
    path = Path(directory) / COOLDOWN_FILE
    if not path.exists():
        return None
    try:
        document = strict_json(read_regular(path, limit=COOLDOWN_LIMIT))
        until = datetime.fromisoformat(document["until"])
    except (KarnError, KeyError, TypeError, ValueError, OverflowError):
        return None
    if until.tzinfo is None:
        return None
    return until if until > (now or datetime.now(UTC)) else None
