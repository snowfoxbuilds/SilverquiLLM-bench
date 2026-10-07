"""Bounded, read-only access to the files the monitor observes; a bad file reads as absent."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from silverquillm.karn.definition import KarnError, read_regular

MAX_DOCUMENT = 64 * 1024 * 1024


def read_json(path: Path, *, limit: int = MAX_DOCUMENT) -> Any:
    """A JSON document from a regular file never followed through a link, else None."""
    try:
        return json.loads(read_regular(path, limit=limit))
    except (KarnError, OSError, ValueError, RecursionError):
        return None


def instant(value: Any) -> datetime | None:
    """An aware UTC time from an ISO 8601 string, else None (Docker's zero time included)."""
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None or moment.year < 2000:
        return None
    return moment.astimezone(UTC)


def mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}
