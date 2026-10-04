"""DeterministicPlayer (V2) — the intent-based test player.

The named ``Intent`` is the scoping/lifecycle layer; answers come from
*preferences* over Player Decisions, which generalize across query
decompositions. The engine raises Player Queries; this player routes each query
to an active Intent by pattern-matching the query's source refs, then answers by
scanning the implementation-ordered options and taking the first option that is
both *intended* (satisfies a preferred decision) and offered — greedy, single
pass, no search. A Baseline Intent handles system-level queries. A query matched
by neither a card intent nor the baseline is an explicit failure.

Priority actions are scripted (see ADR-017): each player holds an ordered
script of action entries, and each Priority Query the player receives consumes
the next one. An entry is one action — :func:`act` (must take effect),
:func:`act_illegal` (must not take effect) or :func:`pass_priority` — and answers
every query raised while its action is being taken that no card intent claims,
so one entry covers an engine that offers a face at once and one that asks for
the face after the card is chosen. A dry script passes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from engine.decisions import (
    AmbiguousIntentError,
    Decision,
    DecisionKind,
    GameRef,
    InvalidPlayerChoiceError,
    PlayerDecision,
    PostconditionError,
    UnmatchedQueryError,
    ref_matches,
    satisfies,
)
from engine.player import Player
from engine.queries import Answer, PlayerQuery, is_priority_query, priority_pattern


@dataclass(frozen=True)
class Intent:
    """A test-scoped query handler.

    ``pattern`` is matched against a query's source refs (subset rule per ref
    field) to route the query; an empty pattern (the Baseline Intent) matches
    every ref. ``preferences`` are scanned in order — the first offered option
    that satisfies a preference wins. ``postcondition`` is checked at
    ``end_intent``. The registry name is passed to ``start_intent``, not stored
    here.

    A ``negative`` intent prefers a choice the rules forbid: an
    ``InvalidPlayerChoiceError`` raised after it answers counts as a pass rather
    than a failure (see ADR-017).
    """

    pattern: GameRef
    preferences: tuple[PlayerDecision, ...] = ()
    postcondition: Callable[[Any], bool] | None = None
    negative: bool = False


_PASS_PRIORITY = Intent(pattern=priority_pattern())


class EntryKind(Enum):
    ACT = "act"
    ILLEGAL = "act_illegal"
    PASS = "pass"


@dataclass(frozen=True)
class ScriptEntry:
    """One priority action in a player's script.

    ``preferences`` choose the action, in order — the first preference any
    offered option satisfies wins, so ``(Decision.obj(printed=GleamOfDeath),
    Decision.obj(printed=GlamdringFoehammer))`` casts Gleam of Death, or casts
    Glamdring and then, when asked which face, Gleam of Death. While the action
    is being taken, ``preferences`` and then ``choices`` answer every query no
    card intent claims (targets, modes, X, payment). ``goal`` is checked once
    the action has taken effect.
    """

    kind: EntryKind
    preferences: tuple[PlayerDecision, ...] = ()
    choices: tuple[PlayerDecision, ...] = ()
    goal: Callable[[Any], bool] | None = None
    label: str = ""

    def describe(self) -> str:
        return self.label or f"{self.kind.value}{_describe(self.preferences)}"


class ScriptEntryError(PostconditionError):
    """A script entry's action did not go as the entry requires.

    ``reason`` is ``"not offered"``, ``"rejected"``, ``"missed goal"`` (for
    :func:`act`) or ``"took effect"`` (for :func:`act_illegal`); ``error`` is the
    ``InvalidPlayerChoiceError`` behind a rejection.
    """

    def __init__(
        self,
        entry: ScriptEntry,
        reason: str,
        error: InvalidPlayerChoiceError | None = None,
    ) -> None:
        detail = f": {error}" if error is not None else ""
        super().__init__(f"script entry {entry.describe()} {reason}{detail}")
        self.entry = entry
        self.reason = reason
        self.error = error


def act(
    *preferences: PlayerDecision | type,
    choices: tuple[PlayerDecision | type, ...] | list[PlayerDecision | type] = (),
    goal: Callable[[Any], bool] | None = None,
    label: str = "",
) -> ScriptEntry:
    """An action the player must take: it fails the test with
    :class:`ScriptEntryError` (a ``PostconditionError``) if no offered option
    satisfies ``preferences``, if the engine rejects it with
    ``InvalidPlayerChoiceError``, or if ``goal(game)`` is falsey once it has
    taken effect.

    A preference may be a Player Decision or a predefined class: a card or
    face class stands for ``Decision.obj(printed=cls)``, an ability or mode
    class for ``Decision.ability(printed=cls)`` or ``Decision.mode(printed=cls)``.
    """
    return ScriptEntry(EntryKind.ACT, _decisions(preferences), _decisions(choices), goal, label)


def act_illegal(
    *preferences: PlayerDecision | type,
    choices: tuple[PlayerDecision | type, ...] | list[PlayerDecision | type] = (),
    label: str = "",
) -> ScriptEntry:
    """An action the rules forbid: it passes if no offered option satisfies
    ``preferences`` or the engine rejects it, and fails the test with
    :class:`ScriptEntryError` if it takes effect. Either way the entry is
    consumed, and the same Priority Query goes to the next entry."""
    return ScriptEntry(EntryKind.ILLEGAL, _decisions(preferences), _decisions(choices), None, label)


def pass_priority(label: str = "") -> ScriptEntry:
    """Pass the priority window that consumes this entry."""
    return ScriptEntry(EntryKind.PASS, label=label)


def _decisions(items: Any) -> tuple[PlayerDecision, ...]:
    decisions: list[PlayerDecision] = []
    for item in items:
        if isinstance(item, PlayerDecision):
            decisions.append(item)
        elif isinstance(item, type):
            decisions.extend(_printed_decisions(item))
        else:
            raise TypeError(
                f"a script preference is a Player Decision or a predefined class, not {item!r}"
            )
    return tuple(decisions)


def _printed_decisions(cls: type) -> tuple[PlayerDecision, ...]:
    from engine.card import CardImpl

    if issubclass(cls, CardImpl):
        return (Decision.obj(printed=cls),)
    return (Decision.ability(printed=cls), Decision.mode(printed=cls))


def _describe(preferences: tuple[PlayerDecision, ...]) -> str:
    parts = []
    for pref in preferences:
        attrs = dict(pref.attrs)
        printed = attrs.get("printed")
        parts.append(printed.__name__ if isinstance(printed, type) else repr(attrs))
    return f"({', '.join(parts)})"


@dataclass
class QueryRecord:
    """One logged query and the answer the player gave (``None`` if it raised).

    ``preference_miss`` is True when a routed *card* intent had preferences but
    none selected any offered option on a ``min > 0`` query — the answer was a
    pure first-offered fill. That usually means a wrong option set or a typo'd
    preference; audits can assert no record has it set.
    """

    query: PlayerQuery
    answer: Answer | None = None
    preference_miss: bool = False

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
        """Logged queries, optionally filtered to the choices offering ``kind``
        options — Priority Queries, which choose an action rather than an
        object or ability, are left out of a filtered list."""
        if kind is None:
            return list(self._records)
        return [
            r
            for r in self._records
            if not is_priority_query(r.query) and any(o.kind is kind for o in r.options)
        ]

    def priority_queries(self) -> list[QueryRecord]:
        """The logged Priority Queries."""
        return [r for r in self._records if is_priority_query(r.query)]


@dataclass
class _EntryAttempt:
    """The script entry whose action is being taken, and how its attempts went.

    Preferences are ranked ``entry.preferences`` then ``entry.choices``; a
    rejected attempt drops the highest-ranked one it used.
    """

    entry: ScriptEntry
    dropped: set[int] = field(default_factory=set)
    used: set[int] = field(default_factory=set)
    error: InvalidPlayerChoiceError | None = None
    retrying: bool = False

    def ranked(self, limit: int | None = None) -> list[tuple[int, PlayerDecision]]:
        prefs = self.entry.preferences + self.entry.choices
        return [(i, p) for i, p in enumerate(prefs[:limit]) if i not in self.dropped]


@dataclass
class _ChoiceAttempt:
    """A resolution-time choice window: which intent preferences the current
    attempt used, and which earlier rejected attempts dropped (by intent key)."""

    dropped: dict[str, set[int]] = field(default_factory=dict)
    used: list[tuple[str, int]] = field(default_factory=list)
    answered: bool = False


_BASELINE_KEY = "<baseline>"


class DeterministicPlayer(Player):
    """Intent-based deterministic player (V2). See module docstring.

    A Priority Query goes to a card intent whose pattern matches it (see
    :func:`~engine.queries.priority_pattern`); with none, it consumes the next
    script entry, and with a dry script the player passes — the Baseline Intent
    never takes an action, whatever its preferences.

    A rejected choice is retried without depending on how the engine presents
    it (see ADR-017): the player drops the highest-ranked preference the
    rejected attempt used and answers the re-asked query with the rest, so
    ``act(GleamOfDeath, GlamdringFoehammer)`` falls back to Glamdring whether
    the engine offered Gleam of Death at once or asked for the face after the
    card. Script position and attempt bookkeeping are decision-side state, so a
    rollback leaves them alone (``rollback_exempt``).
    """

    rollback_exempt = frozenset({
        "_intents", "_baseline", "transcript", "game", "_script", "_attempt",
        "_choices", "_negative_answered", "_pass_next", "last_action_result",
    })

    def __init__(self, name: str, life: int = 20) -> None:
        super().__init__(name, life)
        self._intents: dict[str, Intent] = {}
        self._baseline: Intent | None = None
        self.transcript: Transcript = Transcript()
        # Set by the test harness so end_intent postconditions can read game.
        self.game: Any = None
        self._script: list[ScriptEntry] = []
        self._attempt: _EntryAttempt | None = None
        self._choices: _ChoiceAttempt | None = None
        self._negative_answered = False
        self._pass_next = False
        self.last_action_result: Any = None

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
    # Action script
    # ------------------------------------------------------------------

    def set_script(self, entries: Any) -> list[ScriptEntry]:
        """Replace the action script; return the entries it replaced."""
        replaced, self._script = self._script, list(entries)
        return replaced

    def extend_script(self, entries: Any) -> None:
        self._script.extend(entries)

    @property
    def pending_entries(self) -> tuple[ScriptEntry, ...]:
        """The entries not yet consumed."""
        return tuple(self._script)

    @property
    def acting(self) -> bool:
        """Whether a scripted action is being taken right now."""
        return self._attempt is not None

    def on_choice_rejected(
        self, query: PlayerQuery, answer: Answer, error: InvalidPlayerChoiceError
    ) -> None:
        attempt = self._attempt
        if attempt is None:
            if not self._negative_answered:
                raise error
            # A card intent chose this action; asked again it would choose it
            # again, so the re-asked query is passed.
            self._pass_next = True
            return
        if self._negative_answered or attempt.entry.kind is EntryKind.ILLEGAL:
            self._attempt = None
            return
        if not attempt.used:
            self._attempt = None
            raise ScriptEntryError(attempt.entry, "rejected", error) from error
        attempt.dropped.add(min(attempt.used))
        attempt.error = error
        attempt.retrying = True

    def on_action_taken(self, query: PlayerQuery, answer: Answer, result: Any) -> None:
        attempt, self._attempt = self._attempt, None
        self.last_action_result = result
        if attempt is None:
            return
        if attempt.entry.kind is EntryKind.ILLEGAL:
            raise ScriptEntryError(attempt.entry, "took effect")
        if attempt.entry.goal is not None and not attempt.entry.goal(self.game):
            raise ScriptEntryError(attempt.entry, "missed goal")

    # ------------------------------------------------------------------
    # Resolution-time choices
    # ------------------------------------------------------------------

    def has_choice_preferences(self) -> bool:
        """Whether an intent with preferences could answer a choice now — the
        only case in which a rejected choice can be retried."""
        intents = [*self._intents.values(), self._baseline]
        return any(intent is not None and intent.preferences for intent in intents)

    def begin_choice_window(self) -> None:
        """Start tracking the choices raised while one object resolves."""
        self._choices = _ChoiceAttempt()
        self._negative_answered = False

    def end_choice_window(self) -> None:
        self._choices = None

    def on_resolution_choice_rejected(self, error: InvalidPlayerChoiceError) -> str:
        """Hear that a choice this player made while an object resolved was
        rejected and the game rolled back to before that object resolved.

        Returns ``"pass"`` when a negative intent answered (the rejection counts
        as a pass), ``"retry"`` after dropping the highest-ranked preference the
        first intent to answer used, or ``"none"`` if this player made no choice.

        Raises:
            PostconditionError: if the choice's preferences are exhausted.
        """
        window = self._choices
        if window is None or not window.answered:
            return "none"
        if self._negative_answered:
            return "pass"
        if not window.used:
            raise PostconditionError(
                f"choice rejected with no preference left to drop: {error}"
            ) from error
        key = window.used[0][0]
        dropped = window.dropped.setdefault(key, set())
        dropped.add(min(i for k, i in window.used if k == key))
        intent = self._baseline if key == _BASELINE_KEY else self._intents.get(key)
        if intent is None or len(dropped) >= len(intent.preferences):
            raise PostconditionError(
                f"choice intent {key!r} exhausted its preferences: {error}"
            ) from error
        window.used = []
        window.answered = False
        self._negative_answered = False
        return "retry"

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------

    def answer(self, query: PlayerQuery) -> Answer:
        record = self.transcript._record(query)
        record.answer = self._answer(query, record)
        return record.answer

    def _answer(self, query: PlayerQuery, record: QueryRecord) -> Answer:
        claimed = self._card_intents_for(query)
        if is_priority_query(query):
            self._negative_answered = False
            if self._pass_next:
                self._pass_next = False
                return Answer()
            attempt = self._attempt
            if attempt is not None and attempt.retrying:
                attempt.retrying = False
                attempt.used = set()
                return self._choose_action(attempt, query)
            self._attempt = None
            if self._script and not claimed:
                return self._answer_from_script(query)
        elif self._attempt is not None and not claimed:
            ranked = self._attempt.ranked()
            if _first_preferred([p for _, p in ranked], query.options) is not None:
                answer, used = _select(ranked, query)
                self._attempt.used.update(used)
                return answer

        name, intent = self._route(query, claimed)
        if intent.negative:
            self._negative_answered = True
        window = self._choices
        key = _BASELINE_KEY if name is None else name
        skip = window.dropped.get(key, set()) if window is not None else set()
        ranked = [(i, p) for i, p in enumerate(intent.preferences) if i not in skip]
        answer, used = _select(ranked, query)
        if window is not None and not is_priority_query(query):
            window.answered = True
            window.used.extend((key, i) for i in used)
        if name is not None and intent.preferences and not used and query.min > 0:
            # A routed card intent answered purely by first-offered fill —
            # probable wrong option set or typo'd preference. Flagged in the
            # transcript so audits can catch it; not a hard failure.
            record.preference_miss = True
        return answer

    def _answer_from_script(self, query: PlayerQuery) -> Answer:
        """Consume entries until one answers this Priority Query.

        An :func:`act_illegal` entry whose action is not offered is consumed
        and the query goes to the next entry; a dry script passes.
        """
        while self._script:
            entry = self._script.pop(0)
            if entry.kind is EntryKind.PASS:
                return Answer()
            answer = self._choose_action(_EntryAttempt(entry), query)
            if answer.selected:
                return answer
        return Answer()

    def _choose_action(self, attempt: _EntryAttempt, query: PlayerQuery) -> Answer:
        """Choose ``attempt``'s action from a Priority Query by its remaining
        preferences; an :func:`act` that finds none fails the test."""
        for index, pref in attempt.ranked(len(attempt.entry.preferences)):
            for option in query.options:
                if satisfies(option, pref):
                    attempt.used.add(index)
                    self._attempt = attempt
                    return Answer(selected=(option,))
        self._attempt = None
        if attempt.entry.kind is EntryKind.ACT:
            if attempt.error is not None:
                raise ScriptEntryError(attempt.entry, "rejected", attempt.error) from attempt.error
            raise ScriptEntryError(attempt.entry, "not offered")
        return Answer()

    def _card_intents_for(self, query: PlayerQuery) -> list[tuple[str, Intent]]:
        return [
            (name, intent)
            for name, intent in self._intents.items()
            if _intent_matches(intent, query)
        ]

    def _route(
        self, query: PlayerQuery, matched: list[tuple[str, Intent]]
    ) -> tuple[str | None, Intent]:
        """Return the routed intent and its name (``None`` unless a card intent)."""
        if len(matched) > 1:
            raise AmbiguousIntentError(
                f"{len(matched)} active intents matched query {query.prompt!r}"
            )
        if len(matched) == 1:
            return matched[0]
        if is_priority_query(query):
            return None, _PASS_PRIORITY
        if self._baseline is not None:
            return None, self._baseline
        raise UnmatchedQueryError(
            f"no card intent and no baseline matched query {query.prompt!r}"
        )


def _first_preferred(
    preferences: list[PlayerDecision], options: tuple[PlayerDecision, ...]
) -> PlayerDecision | None:
    """The first option, in implementation order, satisfying the earliest
    preference that any option satisfies."""
    for pref in preferences:
        for option in options:
            if satisfies(option, pref):
                return option
    return None


def _intent_matches(intent: Intent, query: PlayerQuery) -> bool:
    """An intent matches if its pattern subset-matches any source ref."""
    for source in query.source:
        if source.ref is not None and ref_matches(intent.pattern, source.ref):
            return True
    return False


def _select(
    ranked: list[tuple[int, PlayerDecision]], query: PlayerQuery
) -> tuple[Answer, list[int]]:
    """Preference-major greedy selection, then fill to ``min`` in option order.

    Each preference selects the first not-yet-selected offered option that
    satisfies it (this gives ordering queries their order). If more selections
    are required to reach ``min`` (e.g. an ordering query with a partial
    preference list, or a system query with no preferences), the remaining
    options fill in implementation order. ``min == 0`` with no preference match
    yields a decline.

    ``ranked`` pairs each preference with its rank. Returns the Answer and the
    ranks of the preferences that selected an option (as opposed to fill).
    """
    selected: list[PlayerDecision] = []
    used: list[int] = []
    remaining = list(query.options)

    for rank, pref in ranked:
        if len(selected) >= query.max:
            break
        for option in remaining:
            if satisfies(option, pref):
                selected.append(option)
                used.append(rank)
                remaining.remove(option)
                break

    while len(selected) < query.min and remaining:
        selected.append(remaining.pop(0))

    return Answer(selected=tuple(selected)), used
