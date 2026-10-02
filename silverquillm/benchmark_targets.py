"""Resolve legacy collector numbers and explicitly set-qualified targets."""

from __future__ import annotations

import re


def target_cards(primary_set: str, cards: list[str]) -> list[tuple[str, str]]:
    targets = []
    seen = set()
    for value in cards:
        parts = str(value).split(":")
        if len(parts) == 1:
            parts.insert(0, primary_set)
        if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9]+", part) for part in parts):
            raise ValueError(f"Invalid benchmark card: {value!r}")
        set_code, number = parts
        target = (set_code.lower(), str(int(number)) if number.isdigit() else number)
        if target in seen:
            raise ValueError(f"Duplicate benchmark card: {value!r}")
        seen.add(target)
        targets.append((set_code.lower(), number))
    return targets
