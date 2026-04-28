"""Zone containers for managing game objects across game zones."""

from __future__ import annotations

import random
from typing import Any

from engine.types import Zone


class IllegalMoveError(Exception):
    """Raised when a zone move is illegal (e.g. object not found in source zone)."""


class ZoneContainer:
    """Wraps an ordered list of game-object references for a single zone.

    Internal list convention: index 0 is the *bottom*, index -1 is the *top*.
    This matches the intuitive model where ``add(obj, position="top")``
    appends, and ``top(n)`` returns the last *n* items.
    """

    def __init__(self) -> None:
        self._objects: list[Any] = []

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add(self, obj: Any, position: str = "top") -> None:
        """Add *obj* to this zone.

        Parameters:
            obj: The game object to add.
            position: ``"top"`` (default) appends to the end of the internal
                list; ``"bottom"`` inserts at position 0.
        """
        if position == "top":
            self._objects.append(obj)
        elif position == "bottom":
            self._objects.insert(0, obj)
        else:
            raise ValueError(f"Invalid position: {position!r}; expected 'top' or 'bottom'")

    def remove(self, obj: Any) -> None:
        """Remove *obj* from this zone (identity-based lookup).

        Raises:
            ValueError: If *obj* is not in the zone.
        """
        for i, item in enumerate(self._objects):
            if item is obj:
                del self._objects[i]
                return
        raise ValueError(f"{obj!r} not in zone")

    def shuffle(self) -> None:
        """Randomly shuffle the contents of this zone (used for libraries)."""
        random.shuffle(self._objects)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def contains(self, obj: Any) -> bool:
        """Return ``True`` if *obj* is in this zone (identity-based lookup)."""
        return any(item is obj for item in self._objects)

    def get_all(self) -> list[Any]:
        """Return a shallow copy of all objects in order (bottom → top)."""
        return list(self._objects)

    def top(self, n: int) -> list[Any]:
        """Return the top *n* items (last *n* in the internal list).

        If *n* >= len, returns all items.  Order is bottom-to-top (same
        orientation as the internal list).
        """
        if n <= 0:
            return []
        return self._objects[-n:]

    def bottom(self, n: int) -> list[Any]:
        """Return the bottom *n* items (first *n* in the internal list).

        If *n* >= len, returns all items.
        """
        if n <= 0:
            return []
        return self._objects[:n]

    def __len__(self) -> int:
        return len(self._objects)

    def __repr__(self) -> str:
        return f"ZoneContainer({self._objects!r})"


class Zones:
    """Per-player collection mapping each :class:`Zone` to a :class:`ZoneContainer`."""

    def __init__(self, zones: dict[Zone, ZoneContainer]) -> None:
        self._zones = zones

    @classmethod
    def new_player(cls) -> Zones:
        """Create a fresh set of empty zones for a player."""
        return cls({zone: ZoneContainer() for zone in Zone})

    def __getitem__(self, zone: Zone) -> ZoneContainer:
        return self._zones[zone]

    def __contains__(self, zone: Zone) -> bool:
        return zone in self._zones

    def __repr__(self) -> str:
        return f"Zones({self._zones!r})"


def move_zone(
    obj: Any,
    from_zone: ZoneContainer,
    to_zone: ZoneContainer,
    position: str = "top",
) -> None:
    """Move *obj* from *from_zone* to *to_zone*.

    Parameters:
        obj: The game object to move.
        from_zone: Source :class:`ZoneContainer`.
        to_zone: Destination :class:`ZoneContainer`.
        position: ``"top"`` (default), ``"bottom"``, or ``"shuffle"``
            (add then shuffle the destination).

    Raises:
        IllegalMoveError: If *obj* is not in *from_zone*.
    """
    # Moving an object to the same zone it's already in is a no-op.
    if from_zone is to_zone:
        return

    if not from_zone.contains(obj):
        raise IllegalMoveError(
            f"Object {obj!r} not found in source zone"
        )

    # Validate position *before* mutating either zone so that an invalid
    # position does not leave the object removed from the source without
    # being added to the destination.
    if position not in ("top", "bottom", "shuffle"):
        raise ValueError(f"Invalid position: {position!r}; expected 'top', 'bottom', or 'shuffle'")

    from_zone.remove(obj)

    if position == "shuffle":
        to_zone.add(obj, position="top")
        to_zone.shuffle()
    else:
        to_zone.add(obj, position=position)
