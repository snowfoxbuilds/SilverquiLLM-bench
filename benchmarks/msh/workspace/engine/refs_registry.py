"""Game Refs registry — engine-owned instance-id minting and ref assembly.

Mints one opaque instance id per game object *stint* (a zone change yields a
new object, so the same Python object re-mints on every zone arrival — even
when returning to a zone it occupied before, as with a flickered creature).
Instance ids are never test-authored; tests bind to them only dynamically, at
action time, via the object provenance carried on a raised query.
"""

from __future__ import annotations

from typing import Any, Hashable, Mapping

from engine.decisions import Decision, DecisionKind, GameRef, PlayerDecision


def object_options(
    registry: "GameRefsRegistry",
    items: Any,
) -> tuple[tuple[PlayerDecision, ...], dict[PlayerDecision, Any]]:
    """Build OBJECT decisions for ``items`` and a decision→object reverse map.

    ``items`` is an iterable of ``(obj, zone, controller_seat)``. Returns the
    options tuple (in iteration order — the stable game-state-derived order) and
    a mapping so an Answer maps back to the game objects.
    """
    options: list[PlayerDecision] = []
    by_decision: dict[PlayerDecision, Any] = {}
    for obj, zone, controller_seat in items:
        decision = registry.object_decision(
            obj, zone=zone, controller_seat=controller_seat
        )
        if decision in by_decision:
            continue
        options.append(decision)
        by_decision[decision] = obj
    return tuple(options), by_decision


def multi_attrs(obj: Any) -> list[tuple[str, Hashable]]:
    """Return the full (possibly multi-valued) blessed OBJECT attr pairs.

    Unlike :func:`card_attrs` (single-valued convenience), this returns a list
    of ``(key, value)`` pairs so colors/types/subtypes/keywords can each appear
    multiple times — exactly how the frozenset attr-set stores them.
    """
    pairs: list[tuple[str, Hashable]] = []
    name = getattr(obj, "name", None)
    if isinstance(name, str) and name:
        pairs.append(("name", name))
    for t in getattr(obj, "card_types", None) or ():
        pairs.append(("type", getattr(t, "value", t)))
    for s in getattr(obj, "subtypes", None) or ():
        pairs.append(("subtype", s if isinstance(s, str) else getattr(s, "value", s)))
    for color in _colors_of(obj):
        pairs.append(("color", color))
    for kw in _keywords_of(obj):
        pairs.append(("keyword", kw))
    power = getattr(obj, "power", None)
    if isinstance(power, int) and not isinstance(power, bool):
        pairs.append(("power", power))
    toughness = getattr(obj, "toughness", None)
    if isinstance(toughness, int) and not isinstance(toughness, bool):
        pairs.append(("toughness", toughness))
    tapped = getattr(obj, "tapped", getattr(obj, "is_tapped", None))
    if isinstance(tapped, bool):
        pairs.append(("tapped", tapped))
    return pairs


def _colors_of(obj: Any) -> set[str]:
    """Single-letter colors derived from the object's mana cost."""
    colors: set[str] = set()
    cost = getattr(obj, "mana_cost", None)
    if cost is None:
        return colors
    for mt in getattr(cost, "pips", {}) or {}:
        token = getattr(mt, "value", None)
        if token and token != "C":
            colors.add(token)
    for hybrid in getattr(cost, "hybrid", []) or []:
        for opt in (getattr(hybrid, "option_a", None), getattr(hybrid, "option_b", None)):
            token = getattr(opt, "value", None)
            if token and token != "C":
                colors.add(token)
    return colors


def _keywords_of(obj: Any) -> list[str]:
    """Lower-case keyword names present on the object's ``keywords`` flag."""
    kws = getattr(obj, "keywords", None)
    if kws is None:
        return []
    out: list[str] = []
    try:
        for member in type(kws):
            if member in kws:
                out.append(member.name.lower())
    except TypeError:
        return []
    return out


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
    """Mints one opaque instance id per game object *stint* in a zone.

    A zone change yields a new object: every observed zone arrival re-mints,
    including a return to a previously occupied zone (battlefield → exile →
    battlefield is three stints, three ids). Within a stint the id is stable.
    Ids are sequential ints — opaque to tests, which can only observe
    stability/uniqueness, never predict a value.
    """

    def __init__(self) -> None:
        # object identity -> (last observed zone token, current stint id)
        self._current: dict[int, tuple[Hashable, int]] = {}
        self._retain: list[Any] = []  # keep objects alive so id() is not reused
        self._obj_by_id: dict[int, Any] = {}  # instance id -> game object
        self._player_by_seat: dict[int, Any] = {}  # seat -> engine Player
        self._counter: int = 0

    def instance_id(self, obj: Any, zone: Any) -> int:
        """Return the opaque instance id for ``obj``'s current stint in ``zone``.

        Call sites always pass the object's *current* zone, so observing the
        object in a zone other than its last-seen one is a zone arrival and
        mints a fresh id — monotonic, never a cache hit for a revisited zone.
        """
        ztoken = _zone_token(zone)
        current = self._current.get(id(obj))
        if current is not None and current[0] == ztoken:
            return current[1]
        self._counter += 1
        self._current[id(obj)] = (ztoken, self._counter)
        self._obj_by_id[self._counter] = obj
        self._retain.append(obj)
        return self._counter

    def note_zone_change(self, obj: Any) -> None:
        """Invalidate ``obj``'s current stint after an engine zone move.

        Called by ``move_to_zone`` so an *unobserved* stint still breaks id
        continuity: a flickered object whose exile stint no query ever sees
        must not get its pre-flicker id back on return. Minting stays lazy —
        the next observation re-mints.
        """
        self._current.pop(id(obj), None)

    # ------------------------------------------------------------------
    # Player registration / reverse lookup
    # ------------------------------------------------------------------

    def register_player(self, player: Any, seat: int) -> None:
        """Record the seat ↔ Player correlation (called once at game setup)."""
        self._player_by_seat[seat] = player

    def seat_of(self, player: Any) -> int | None:
        """Return the seat for a registered Player (identity match)."""
        for seat, candidate in self._player_by_seat.items():
            if candidate is player:
                return seat
        return None

    def player_decision(
        self, player: Any, *, seat: int, role: str | None = None
    ) -> PlayerDecision:
        """Build the PLAYER decision for ``player`` and record the correlation."""
        self._player_by_seat[seat] = player
        attrs: dict[str, Hashable] = {"seat": seat}
        name = getattr(player, "name", None)
        if isinstance(name, str) and name:
            attrs["name"] = name
        if role is not None:
            attrs["role"] = role
        return Decision.player(ref=GameRef(player=frozenset({("seat", seat)})), **attrs)

    # ------------------------------------------------------------------
    # Object decisions / reverse lookup
    # ------------------------------------------------------------------

    def object_decision(
        self,
        obj: Any,
        *,
        zone: Any,
        controller_seat: int | None = None,
        card: Mapping[str, Hashable] | None = None,
    ) -> PlayerDecision:
        """Build the OBJECT decision for ``obj`` and record the correlation.

        attrs carry the minted instance id, the zone token, and the object's
        intrinsic blessed facts (name/colors/types/subtypes/keywords/p/t/tapped)
        plus controller seat. The ref carries the instance (for binding) and the
        card name (printed identity, for routing).
        """
        iid = self.instance_id(obj, zone)
        ztoken = _zone_token(zone)
        attrs: list[tuple[str, Hashable]] = [("instance", iid), ("zone", ztoken)]
        attrs.extend(multi_attrs(obj))
        if controller_seat is not None:
            attrs.append(("controller", controller_seat))
        card_ref: dict[str, Hashable] = dict(card or {})
        name = getattr(obj, "name", None)
        if isinstance(name, str) and name and "name" not in card_ref:
            card_ref["name"] = name
        ref = GameRef(
            object=frozenset({("instance", iid)}),
            zone=frozenset({("name", ztoken)}),
            card=frozenset(card_ref.items()),
            player=(
                frozenset({("seat", controller_seat)})
                if controller_seat is not None
                else frozenset()
            ),
        )
        return PlayerDecision(
            kind=DecisionKind.OBJECT,
            attrs=frozenset(attrs),
            ref=ref,
        )

    def object_for(self, decision: PlayerDecision) -> Any:
        """Map an OBJECT/PLAYER Answer decision back to the game object/player."""
        for key, value in decision.attrs:
            if key == "instance":
                return self._obj_by_id.get(value)
            if key == "seat":
                return self._player_by_seat.get(value)
        # Fall back to the ref provenance.
        if decision.ref is not None:
            for key, value in decision.ref.object:
                if key == "instance":
                    return self._obj_by_id.get(value)
            for key, value in decision.ref.player:
                if key == "seat":
                    return self._player_by_seat.get(value)
        return None

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
