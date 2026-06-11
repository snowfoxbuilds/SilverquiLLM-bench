"""DeterministicPlayer (MSH) — the intent-based test player.

The named ``Intent`` is the scoping/lifecycle layer; answers come from
*preferences* over Player Decisions, which generalize across query
decompositions. The engine raises Player Queries; this player routes each query
to an active Intent by pattern-matching the query's source refs, then answers by
scanning the implementation-ordered options and taking the first option that is
both *intended* (satisfies a preferred decision) and offered — greedy, single
pass, no search. A Baseline Intent handles system-level queries. A query matched
by neither a card intent nor the baseline is an explicit failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from engine.decisions import (
    AmbiguousIntentError,
    DecisionKind,
    GameRef,
    PlayerDecision,
    PostconditionError,
    UnmatchedQueryError,
    ref_matches,
    satisfies,
)
from engine.player import Player
from engine.queries import Answer, PlayerQuery


@dataclass(frozen=True)
class Intent:
    """A test-scoped query handler.

    ``pattern`` is matched against a query's source refs (subset rule per ref
    field) to route the query; an empty pattern (the Baseline Intent) matches
    every ref. ``preferences`` are scanned in order — the first offered option
    that satisfies a preference wins. ``postcondition`` is checked at
    ``end_intent``. The registry name is passed to ``start_intent``, not stored
    here.
    """

    pattern: GameRef
    preferences: tuple[PlayerDecision, ...] = ()
    postcondition: Callable[[Any], bool] | None = None


@dataclass
class QueryRecord:
    """One logged query and the answer the player gave (``None`` if it raised)."""

    query: PlayerQuery
    answer: Answer | None = None

    @property
    def options(self) -> tuple[PlayerDecision, ...]:
        return self.query.options

    @property
    def source(self) -> tuple[PlayerDecision, ...]:
        return self.query.source

    @property
    def min(self) -> int:
        return self.query.min

    @property
    def max(self) -> int:
        return self.query.max


class Transcript:
    """Append-only log of every query raised (for option-set invariants)."""

    def __init__(self) -> None:
        self._records: list[QueryRecord] = []

    def _record(self, query: PlayerQuery) -> QueryRecord:
        record = QueryRecord(query=query)
        self._records.append(record)
        return record

    def all(self) -> list[QueryRecord]:
        return list(self._records)

    def queries(self, kind: DecisionKind | None = None) -> list[QueryRecord]:
        """Logged queries, optionally filtered to those offering ``kind`` options."""
        if kind is None:
            return list(self._records)
        return [
            r for r in self._records if any(o.kind is kind for o in r.options)
        ]


class DeterministicPlayer(Player):
    """Intent-based deterministic player (MSH). See module docstring."""

    def __init__(self, name: str, life: int = 20) -> None:
        super().__init__(name, life)
        self._intents: dict[str, Intent] = {}
        self._baseline: Intent | None = None
        self.transcript: Transcript = Transcript()
        # Set by the test harness so end_intent postconditions can read game.
        self.game: Any = None

    # ------------------------------------------------------------------
    # Intent lifecycle
    # ------------------------------------------------------------------

    def start_intent(self, name: str, intent: Intent) -> None:
        """Activate a card intent under ``name``."""
        self._intents[name] = intent

    def end_intent(self, name: str, game: Any = None) -> None:
        """Deactivate ``name`` and check its postcondition.

        Raises:
            KeyError: if ``name`` was never started.
            PostconditionError: if the intent's postcondition returns falsey.
        """
        intent = self._intents.pop(name)
        if intent.postcondition is not None:
            g = game if game is not None else self.game
            if not intent.postcondition(g):
                raise PostconditionError(
                    f"postcondition for intent {name!r} did not hold"
                )

    def set_baseline(self, intent: Intent) -> None:
        """Set the single Baseline Intent (replacing any prior baseline)."""
        self._baseline = intent

    def clear_baseline(self) -> None:
        self._baseline = None

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------

    def answer(self, query: PlayerQuery) -> Answer:
        record = self.transcript._record(query)
        intent = self._route(query)
        answer = _answer_with_intent(intent, query)
        record.answer = answer
        return answer

    def _route(self, query: PlayerQuery) -> Intent:
        matched = [
            intent
            for intent in self._intents.values()
            if _intent_matches(intent, query)
        ]
        if len(matched) > 1:
            raise AmbiguousIntentError(
                f"{len(matched)} active intents matched query {query.prompt!r}"
            )
        if len(matched) == 1:
            return matched[0]
        if self._baseline is not None:
            return self._baseline
        raise UnmatchedQueryError(
            f"no card intent and no baseline matched query {query.prompt!r}"
        )


def _intent_matches(intent: Intent, query: PlayerQuery) -> bool:
    """An intent matches if its pattern subset-matches any source ref."""
    for source in query.source:
        if source.ref is not None and ref_matches(intent.pattern, source.ref):
            return True
    return False


def _answer_with_intent(intent: Intent, query: PlayerQuery) -> Answer:
    """Preference-major greedy selection, then fill to ``min`` in option order.

    Each preference selects the first not-yet-selected offered option that
    satisfies it (this gives ordering queries their order). If more selections
    are required to reach ``min`` (e.g. an ordering query with a partial
    preference list, or a system query with no preferences), the remaining
    options fill in implementation order. ``min == 0`` with no preference match
    yields a decline.
    """
    selected: list[PlayerDecision] = []
    remaining = list(query.options)

    for pref in intent.preferences:
        if len(selected) >= query.max:
            break
        for option in remaining:
            if satisfies(option, pref):
                selected.append(option)
                remaining.remove(option)
                break

    while len(selected) < query.min and remaining:
        selected.append(remaining.pop(0))

    return Answer(selected=tuple(selected))
