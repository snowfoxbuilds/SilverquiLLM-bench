"""Bounded, read-only access to the files the monitor observes; a bad file reads as absent."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from silverquillm.karn.definition import KarnError, read_regular

MAX_DOCUMENT = 64 * 1024 * 1024
# Far above any real request's price; summing amounts past Decimal's exponent range raises.
MAX_USD = Decimal(10) ** 12


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
    try:
        return moment.astimezone(UTC)
    except OverflowError:  # year 9999 behind UTC
        return None


def number(value: Any) -> float | None:
    """A finite float from a JSON number; an integer too large for a float is None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        value = float(value)
    except OverflowError:
        return None
    return value if math.isfinite(value) else None


def mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}
