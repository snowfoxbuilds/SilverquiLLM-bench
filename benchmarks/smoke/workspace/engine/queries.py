"""Player Query layer — PlayerQuery, Answer, and boundary validation.

A Player Query is the engine's native question to a player. Boundary validation
runs engine-side as each query is raised: an unknown kind, malformed attrs, or
an unstable/empty/duplicated option set is an explicit, attributable engine
failure (``ProtocolError`` family) — these signals replace ``ScriptExhaustedError``.

An Answer is a selection of between ``min`` and ``max`` options; the engine
validates every Answer before applying it. An answer violation is a *test* bug
(``InvalidAnswerError``), not an engine bug.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from engine import attempts
from engine.decisions import (
    DecisionKind,
    GameRef,
    InvalidAnswerError,
    InvalidOptionsError,
    MalformedAttrsError,
    PlayerDecision,
    UnknownKindError,
    satisfies,
    validate_attrs,
)

# The ``ability`` ref entry that marks a Priority Query's source (see ADR-017).
PRIORITY_WINDOW: tuple[str, str] = ("window", "priority")


@dataclass(frozen=True)
class PlayerQuery:
    """A question raised to a player.

    ``source`` = the Player Decisions that raised it (routing matches on their
    refs). ``options`` = the legal choices in implementation-provided stable
    order (part of the contract). ``min``/``max`` = how many must / may be
    chosen; ``min == 0`` means legally declinable. ``question`` = an optional
    annotation of what the query asks for, when several questions are possible
    in one situation — canonical objects only: Game Symbols such as
    ``CardType.ARTIFACT``, predefined classes, Game Refs, or Player Decisions
    built from them (see :func:`asks_for`). An engine need not attach one;
    tests read it best-effort.
    """

    source: tuple[PlayerDecision, ...]
    prompt: str
    options: tuple[PlayerDecision, ...]
    min: int
    max: int
    question: tuple[Any, ...] = ()


def asks_for(query: PlayerQuery, wanted: Any) -> bool:
    """Whether ``query``'s question payload holds ``wanted``: a payload
    Player Decision that satisfies it, as an option satisfies a preference, or
    the same object otherwise."""
    for item in query.question:
        if isinstance(wanted, PlayerDecision) and isinstance(item, PlayerDecision):
            if satisfies(item, wanted):
                return True
        elif item is wanted or item == wanted:
            return True
    return False


# The modules whose enums are the engine's Game Symbols.
_SYMBOL_MODULES = frozenset({"engine.types", "engine.decisions"})


def _canonical(value: Any) -> bool:
    """Whether ``value`` may annotate a question: a Game Symbol, a predefined
    class, a Game Ref, or a Player Decision with valid attrs — never a raw
    string or a custom symbol."""
    if isinstance(value, enum.Enum):
        return type(value).__module__ in _SYMBOL_MODULES
    if isinstance(value, type):
        return value.__module__ != "builtins" and not issubclass(value, enum.Enum)
    if isinstance(value, GameRef):
        return True
    if isinstance(value, PlayerDecision):
        try:
            validate_attrs(value.kind, dict(value.attrs), strict=False)
        except MalformedAttrsError:
            return False
        return True
    return False


@dataclass(frozen=True)
class Answer:
    """A selection of options. Decline is ``Answer(selected=())``.

    Each element must equal one of ``query.options``; no duplicates;
    ``min <= len(selected) <= max``. Validated by the engine before applying.
    """

    selected: tuple[PlayerDecision, ...] = field(default_factory=tuple)


def priority_pattern(seat: int | None = None) -> GameRef:
    """The Intent pattern that matches Priority Queries, optionally for one seat.

    A Priority Query's single source is the PLAYER decision for the player
    receiving priority; its ref carries that player's seat and
    :data:`PRIORITY_WINDOW`, so a card intent patterned on card identity never
    matches it.
    """
    player = frozenset({("seat", seat)}) if seat is not None else frozenset()
    return GameRef(player=player, ability=frozenset({PRIORITY_WINDOW}))


def is_priority_query(query: PlayerQuery) -> bool:
    """Whether ``query`` is a Priority Query — the player's choice of action."""
    return any(
        source.ref is not None and PRIORITY_WINDOW in source.ref.ability
        for source in query.source
    )


def validate_query(query: PlayerQuery) -> None:
    """Boundary-validate a query as it is raised (engine-fault on failure)."""
    if not isinstance(query.question, tuple) or not all(map(_canonical, query.question)):
        raise MalformedAttrsError(
            f"question payload {query.question!r} must hold only Game Symbols, predefined "
            "classes, Game Refs or Player Decisions"
        )
    if query.min < 0 or query.max < query.min:
        raise InvalidOptionsError(
            f"invalid bounds: min={query.min}, max={query.max}"
        )

    n = len(query.options)
    if n == 0:
        if query.min > 0:
            raise InvalidOptionsError("empty options with min > 0")
        return

    if query.max > n:
        raise InvalidOptionsError(
            f"max {query.max} exceeds option count {n}"
        )

    seen: set[PlayerDecision] = set()
    for opt in query.options:
        if not isinstance(opt, PlayerDecision):
            raise InvalidOptionsError(f"malformed option: {opt!r}")
        if not isinstance(opt.kind, DecisionKind):
            raise UnknownKindError(f"option kind {opt.kind!r} is not a DecisionKind")
        # Re-validate attrs against the blessed schema. Engines may attach
        # surplus attrs (inert for satisfies()), so this check is lenient on
        # unknown keys but still rejects out-of-domain values for blessed keys.
        validate_attrs(opt.kind, dict(opt.attrs), strict=False)
        if opt in seen:
            raise InvalidOptionsError(f"duplicate option: {opt!r}")
        seen.add(opt)


def ask(player: object, query: PlayerQuery) -> Answer:
    """Route a query to a player through the boundary validator.

    The single choke point for every engine→player interaction: the query is
    boundary-validated (engine-fault on failure) *before* it reaches the player,
    and the returned Answer is validated (test-fault on failure) before the
    engine applies it.
    """
    validate_query(query)
    context = attempts.current()
    if context is not None:
        context.before_query(player)
    answer = player.answer(query)  # type: ignore[attr-defined]
    validate_answer(query, answer)
    return answer


def validate_answer(query: PlayerQuery, answer: Answer) -> None:
    """Validate an Answer against its query (test-fault on failure)."""
    selected = answer.selected
    if not (query.min <= len(selected) <= query.max):
        raise InvalidAnswerError(
            f"selected {len(selected)} not in [{query.min}, {query.max}]"
        )
    seen: set[PlayerDecision] = set()
    for decision in selected:
        if decision not in query.options:
            raise InvalidAnswerError(f"selection {decision!r} is not an offered option")
        if decision in seen:
            raise InvalidAnswerError(f"duplicate selection: {decision!r}")
        seen.add(decision)
