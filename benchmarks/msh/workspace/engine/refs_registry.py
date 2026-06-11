"""Game Refs registry — engine-owned instance-id minting and ref assembly.

Mints one opaque instance id per game object (a zone change yields a new
object, so the same Python object in a new zone re-mints). Instance ids are
never test-authored; tests bind to them only dynamically, at action time, via
the object provenance carried on a raised query.
"""

from __future__ import annotations

from typing import Any, Hashable, Mapping

from engine.decisions import GameRef


def _zone_token(zone: Any) -> Hashable:
    """Normalize a zone identifier (str or Zone enum) to a stable token."""
    if isinstance(zone, str):
        return zone
    # engine.types.Zone has a ``.value`` (str); fall back to ``.name`` / str.
    value = getattr(zone, "value", None)
    if isinstance(value, str):
        return value
    name = getattr(zone, "name", None)
    if isinstance(name, str):
        return name.lower()
    return str(zone)


class GameRefsRegistry:
    """Mints opaque instance ids keyed by (object identity, zone).

    A zone change yields a new object: the same object queried in a different
    zone gets a fresh id. Ids are sequential ints — opaque to tests, which can
    only observe stability/uniqueness, never predict a value.
    """

    def __init__(self) -> None:
        self._ids: dict[tuple[int, Hashable], int] = {}
        self._retain: list[Any] = []  # keep objects alive so id() is not reused
        self._counter: int = 0

    def instance_id(self, obj: Any, zone: Any) -> int:
        """Return the opaque instance id for ``obj`` as of ``zone``."""
        key = (id(obj), _zone_token(zone))
        existing = self._ids.get(key)
        if existing is not None:
            return existing
        self._counter += 1
        self._ids[key] = self._counter
        self._retain.append(obj)
        return self._counter

    def ref_for(
        self,
        obj: Any,
        *,
        zone: Any,
        card: Mapping[str, Hashable] | None = None,
        player: Mapping[str, Hashable] | None = None,
        ability: Mapping[str, Hashable] | None = None,
    ) -> GameRef:
        """Assemble a :class:`GameRef` for ``obj``.

        The object field carries the engine-minted ``("instance", id)``; the
        zone field carries ``("name", <zone token>)`` provenance; ``card`` /
        ``player`` / ``ability`` provenance is passed through verbatim.
        """
        iid = self.instance_id(obj, zone)
        return GameRef(
            object=frozenset({("instance", iid)}),
            zone=frozenset({("name", _zone_token(zone))}),
            card=frozenset((card or {}).items()),
            player=frozenset((player or {}).items()),
            ability=frozenset((ability or {}).items()),
        )
