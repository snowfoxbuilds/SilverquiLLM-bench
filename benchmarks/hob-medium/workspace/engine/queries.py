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

from dataclasses import dataclass, field

from engine.decisions import (
    DecisionKind,
    InvalidAnswerError,
    InvalidOptionsError,
    PlayerDecision,
    UnknownKindError,
    validate_attrs,
)


@dataclass(frozen=True)
class PlayerQuery:
    """A question raised to a player.

    ``source`` = the Player Decisions that raised it (routing matches on their
    refs). ``options`` = the legal choices in implementation-provided stable
    order (part of the contract). ``min``/``max`` = how many must / may be
    chosen; ``min == 0`` means legally declinable.
    """

    source: tuple[PlayerDecision, ...]
    prompt: str
    options: tuple[PlayerDecision, ...]
    min: int
    max: int


@dataclass(frozen=True)
class Answer:
    """A selection of options. Decline is ``Answer(selected=())``.

    Each element must equal one of ``query.options``; no duplicates;
    ``min <= len(selected) <= max``. Validated by the engine before applying.
    """

    selected: tuple[PlayerDecision, ...] = field(default_factory=tuple)


def validate_query(query: PlayerQuery) -> None:
    """Boundary-validate a query as it is raised (engine-fault on failure)."""
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
