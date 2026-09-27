"""Player Decision data layer — the Game Symbols vocabulary.

Immutable, hashable, serializable structs for the V2 Player Query / Player
Decision protocol: ``DecisionKind``, ``PlayerDecision``, ``GameRef``, the free
function ``satisfies()``, and the engine/test exception hierarchy.

``satisfies()`` is a free function, never a method — subsumption is a relation,
not inheritance, and no method body exists for per-card logic to leak into.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Hashable, Mapping


# ---------------------------------------------------------------------------
# Exception hierarchy — engine-fault vs test-fault split
# ---------------------------------------------------------------------------


class ProtocolError(Exception):
    """Base: engine-side protocol failure (attributable to the engine)."""


class UnknownKindError(ProtocolError):
    """A query option's kind is not a :class:`DecisionKind`."""


class MalformedAttrsError(ProtocolError):
    """An attr key/value lies outside the blessed per-kind schema."""


class InvalidOptionsError(ProtocolError):
    """Empty options with ``min > 0``, a malformed option, or unstable order."""


class IntentError(Exception):
    """Base: test-authoring failure (attributable to the test)."""


class AmbiguousIntentError(IntentError):
    """Two active intents matched one query."""


class UnmatchedQueryError(IntentError):
    """No card intent and no baseline intent matched a raised query."""


class InvalidAnswerError(IntentError):
    """An Answer violates min/max or options membership, or has duplicates."""


class PostconditionError(IntentError):
    """An ``end_intent`` postcondition failed."""


class DecisionKind(enum.Enum):
    """Closed, benchmark-owned set of Player Decision kinds.

    Frozen per checkpoint; adding a kind is a benchmark-version event.
    """

    PLAYER = "player"
    OBJECT = "object"
    ABILITY = "ability"
    MANA = "mana"
    NUMBER = "number"
    BOOL = "bool"
    MODE = "mode"
    COLOR = "color"


@dataclass(frozen=True)
class PlayerDecision:
    """One unit of choice: kind + structural attrs + Modifiers + optional ref.

    ``attrs`` = *what the choice is* (intents constrain on these; visible to
    ``satisfies()``). ``modifiers`` = refinements (read only by engine spend
    predicates and audit assertions; invisible to ``satisfies()``). ``ref`` =
    provenance (routing/correlation; invisible to ``satisfies()``); ``None`` for
    pure values (yes/no, numbers, colors).
    """

    kind: DecisionKind
    attrs: frozenset[tuple[str, Hashable]] = frozenset()
    modifiers: frozenset[tuple[str, Hashable]] = frozenset()
    ref: "GameRef | None" = None


def satisfies(specific: PlayerDecision, general: PlayerDecision) -> bool:
    """Return True iff ``specific`` is subsumed by ``general``.

    Same kind and ``general.attrs`` is a subset of ``specific.attrs``. Modifiers
    and ref are invisible — never compared, never special-cased per kind.
    """
    return specific.kind == general.kind and general.attrs <= specific.attrs


@dataclass(frozen=True)
class GameRef:
    """Hierarchical provenance for a Player Decision.

    Each field is a mini attr-set in the Game Symbols vocabulary, so the single
    subset-matching primitive (:func:`ref_matches`) is reused per field. Any
    field may be empty. ``card`` is printed identity (static, test-knowable);
    ``object`` is the instance and carries the opaque engine-minted instance id
    (a zone change yields a new object).
    """

    player: frozenset[tuple[str, Hashable]] = field(default_factory=frozenset)
    zone: frozenset[tuple[str, Hashable]] = field(default_factory=frozenset)
    card: frozenset[tuple[str, Hashable]] = field(default_factory=frozenset)
    object: frozenset[tuple[str, Hashable]] = field(default_factory=frozenset)
    ability: frozenset[tuple[str, Hashable]] = field(default_factory=frozenset)


def ref_matches(pattern: GameRef, actual: GameRef) -> bool:
    """Return True iff every field of ``pattern`` subset-matches ``actual``.

    The same subset rule used by :func:`satisfies` for attrs, applied per ref
    field. An empty pattern field matches anything (``frozenset() <= x``); an
    all-empty pattern (the Baseline Intent pattern) matches every ref.
    """
    return (
        pattern.player <= actual.player
        and pattern.zone <= actual.zone
        and pattern.card <= actual.card
        and pattern.object <= actual.object
        and pattern.ability <= actual.ability
    )


# ---------------------------------------------------------------------------
# Game Symbols vocabulary — the blessed, frozen-per-checkpoint schema
# ---------------------------------------------------------------------------

COLORS: frozenset[str] = frozenset({"W", "U", "B", "R", "G", "C"})
ZONES: frozenset[str] = frozenset(
    {"battlefield", "hand", "graveyard", "library", "exile", "stack", "command"}
)
PLAYER_ROLES: frozenset[str] = frozenset(
    {"controller", "opponent", "active", "nonactive", "you", "owner"}
)

# Canonical Modifier names: Modifiers are open (engines may invent private
# ones), but any Modifier an audited test asserts on must use a canonical name.
CANONICAL_MODIFIERS: frozenset[str] = frozenset({"spend", "snow"})

# Per-kind blessed attr keys -> value domain. Domain may be a set/frozenset
# (membership), a type (isinstance), a callable predicate, or None (any
# hashable). This mapping *is* the closed attr schema enforced by the smart
# constructors and by boundary validation.
ATTR_SCHEMA: dict[DecisionKind, dict[str, Any]] = {
    DecisionKind.OBJECT: {
        "instance": None,
        "zone": ZONES,
        "color": COLORS,
        "type": str,
        "subtype": str,
        "name": str,
        "controller": None,
        "owner": None,
        "keyword": str,
        "tapped": bool,
        "power": int,
        "toughness": int,
    },
    DecisionKind.PLAYER: {
        "instance": None,
        "name": str,
        "seat": int,
        "role": PLAYER_ROLES,
    },
    DecisionKind.ABILITY: {
        "instance": None,
        "index": int,
        "source": None,
        "keyword": str,
    },
    DecisionKind.MANA: {
        "color": COLORS,
    },
    DecisionKind.NUMBER: {
        "value": int,
    },
    DecisionKind.BOOL: {
        "value": bool,
    },
    DecisionKind.MODE: {
        "name": str,
        "index": int,
    },
    DecisionKind.COLOR: {
        "color": COLORS,
    },
}


def _value_ok(domain: Any, value: Any) -> bool:
    if domain is None:
        return True
    if isinstance(domain, (set, frozenset)):
        return value in domain
    if isinstance(domain, type):
        # bool is a subclass of int; keep them distinct for value/tapped attrs.
        if domain is int and isinstance(value, bool):
            return False
        return isinstance(value, domain)
    if callable(domain):
        return bool(domain(value))
    return False


def validate_attrs(
    kind: DecisionKind,
    attrs: Mapping[str, Hashable],
    *,
    strict: bool = True,
) -> frozenset[tuple[str, Hashable]]:
    """Validate ``attrs`` against the blessed schema for ``kind``.

    Returns the frozenset form. Raises :class:`MalformedAttrsError` for an
    out-of-domain value on a blessed key or a non-hashable value. When
    ``strict`` is True (the smart-constructor gate for intent and oracle
    authors), an unknown key is also a malformed-attrs error. When ``strict``
    is False (the engine-boundary check), unknown keys are tolerated so engines
    may attach surplus attrs that stay inert under :func:`satisfies`.
    """
    blessed = ATTR_SCHEMA.get(kind)
    if blessed is None:
        raise MalformedAttrsError(f"no attr schema for kind {kind!r}")
    out: list[tuple[str, Hashable]] = []
    for key, value in attrs.items():
        if not isinstance(value, Hashable):
            raise MalformedAttrsError(f"attr {key!r} value {value!r} is not hashable")
        if key not in blessed:
            if strict:
                raise MalformedAttrsError(
                    f"attr key {key!r} is not blessed for {kind.name} "
                    f"(blessed: {sorted(blessed)})"
                )
            # Surplus attr from an engine: tolerated, inert for matching.
            out.append((key, value))
            continue
        if not _value_ok(blessed[key], value):
            raise MalformedAttrsError(
                f"attr {key}={value!r} is outside the blessed domain for {kind.name}"
            )
        out.append((key, value))
    return frozenset(out)


def _make(
    kind: DecisionKind,
    attrs: Mapping[str, Hashable],
    modifiers: Mapping[str, Hashable] | None = None,
    ref: GameRef | None = None,
) -> PlayerDecision:
    return PlayerDecision(
        kind=kind,
        attrs=validate_attrs(kind, attrs),
        modifiers=frozenset((modifiers or {}).items()),
        ref=ref,
    )


class Decision:
    """Smart constructors — the only sanctioned way to build Player Decisions.

    The constructors *are* the schema: they validate attrs against the blessed
    per-kind vocabulary (raising :class:`MalformedAttrsError`) so an intent that
    accidentally requires a restriction is unrepresentable. Modifiers are open.
    """

    @staticmethod
    def obj(ref: GameRef | None = None, **attrs: Hashable) -> PlayerDecision:
        return _make(DecisionKind.OBJECT, attrs, ref=ref)

    @staticmethod
    def player(ref: GameRef | None = None, **attrs: Hashable) -> PlayerDecision:
        return _make(DecisionKind.PLAYER, attrs, ref=ref)

    @staticmethod
    def ability(ref: GameRef | None = None, **attrs: Hashable) -> PlayerDecision:
        return _make(DecisionKind.ABILITY, attrs, ref=ref)

    @staticmethod
    def mana(
        color: str,
        spend: Hashable | None = None,
        ref: GameRef | None = None,
        **modifiers: Hashable,
    ) -> PlayerDecision:
        mods: dict[str, Hashable] = dict(modifiers)
        if spend is not None:
            mods["spend"] = spend
        return _make(DecisionKind.MANA, {"color": color}, modifiers=mods, ref=ref)

    @staticmethod
    def number(n: int) -> PlayerDecision:
        return _make(DecisionKind.NUMBER, {"value": n})

    @staticmethod
    def yes() -> PlayerDecision:
        return _make(DecisionKind.BOOL, {"value": True})

    @staticmethod
    def no() -> PlayerDecision:
        return _make(DecisionKind.BOOL, {"value": False})

    @staticmethod
    def boolean(b: bool) -> PlayerDecision:
        return Decision.yes() if b else Decision.no()

    @staticmethod
    def color(c: str) -> PlayerDecision:
        return _make(DecisionKind.COLOR, {"color": c})

    @staticmethod
    def mode(name: str, index: int | None = None) -> PlayerDecision:
        attrs: dict[str, Hashable] = {"name": name}
        if index is not None:
            attrs["index"] = index
        return _make(DecisionKind.MODE, attrs)
