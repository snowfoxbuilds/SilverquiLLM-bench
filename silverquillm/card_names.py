"""Card name resolution — builds card_id → card_name mapping.

Used by slow-cadence artifact writers (status.json, result.json, progress.jsonl)
and the terminal print layer to display human-readable card names alongside IDs.

The source of truth is card_spec.json files under cards/{set_code}/{card_id}/.
snapshot_telemetry.jsonl stays IDs-only per the SETTLED scope carve-out.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def build_card_name_map(cards_dir: Path, set_code: str = "sos") -> dict[str, str]:
    """Build a mapping from card_id (directory name) to card name.

    Parameters
    ----------
    cards_dir:
        Root cards directory (e.g. <repo>/cards).
    set_code:
        Set code subdirectory (default: "sos").

    Returns
    -------
    dict[str, str]
        Mapping of card directory name → card name from card_spec.json.
        E.g. {"sos_1": "The Dawning Archaic", "sos_7": "Antiquities on the Loose"}
    """
    name_map: dict[str, str] = {}
    set_dir = cards_dir / set_code
    if not set_dir.exists():
        return name_map

    for child in set_dir.iterdir():
        if not child.is_dir():
            continue
        spec_file = child / "card_spec.json"
        if spec_file.exists():
            try:
                with open(spec_file, "r", encoding="utf-8") as f:
                    spec = json.load(f)
                card_name = spec.get("name", "")
                if card_name:
                    name_map[child.name] = card_name
            except (json.JSONDecodeError, OSError):
                continue

    return name_map


# Pre-compiled regex for card ID patterns (e.g. sos_1, sos_7, fdn_42)
_CARD_ID_PATTERN = re.compile(r"\b([a-z]{2,4}_\d+)\b")


def resolve_card_names_in_line(line: str, name_map: dict[str, str]) -> str:
    """Resolve card IDs to include names in a terminal output line.

    For each card_id found in the line that exists in name_map,
    appends the card name after the ID: "sos_1" → "sos_1 The Dawning Archaic".

    Parameters
    ----------
    line:
        A terminal output line that may contain card IDs.
    name_map:
        Mapping from card_id to card_name.

    Returns
    -------
    str
        The line with card names resolved inline.
    """
    if not name_map:
        return line

    def _replace(match: re.Match) -> str:
        card_id = match.group(1)
        name = name_map.get(card_id)
        if name:
            return f"{card_id} {name}"
        return card_id

    return _CARD_ID_PATTERN.sub(_replace, line)
