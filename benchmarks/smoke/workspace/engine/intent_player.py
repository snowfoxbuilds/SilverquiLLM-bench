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

What happens after a rejection is written by the test, never inferred: an entry
or intent holds ordered *branches*, each an ordinary preference list answering
every query of an attempt, and a rejected attempt is retried with the next
branch. One preference list is one branch, so its rejection fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping

from engine import attempts
from engine.attempts import AttemptAnswer
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
from engine.queries import Answer, PlayerQuery, asks_for, is_priority_query, priority_pattern


@dataclass(frozen=True)
class Intent:
    """A test-scoped query handler.

    ``pattern`` is matched against a query's source refs (subset rule per ref
    field) to route the query; an empty pattern (the Baseline Intent) matches
    every ref. ``preferences`` are scanned in order — the first offered option
    that satisfies a preference wins. ``postcondition`` is checked at
    ``end_intent``. The registry name is passed to ``start_intent``, not stored
    here.

    ``branches`` replaces ``preferences`` when a rejected choice should be
    retried: each branch is a preference list or a :func:`branch`, the first
    answers the attempt, and each rejection the intent owns retries the
    attempt with the next one. With ``preferences`` alone there is one branch,
    and its rejection fails the test (see ADR-017). ``per_query`` maps what a
    query asks for to the preferences that answer it, as in :func:`branch`.

    A ``negative`` intent prefers a choice the rules forbid: when the engine
    rejects that choice with ``InvalidPlayerChoiceError``, the rejection counts
    as a pass; when the choice takes effect, the test fails with
    ``PostconditionError`` — at the end of the attempt it was made in, or at
    ``end_intent`` (see ADR-017). If no forbidden choice is offered, nothing
    is checked.
    """

    pattern: GameRef
    preferences: tuple[PlayerDecision, ...] = ()
    postcondition: Callable[[Any], bool] | None = None
    negative: bool = False
    branches: tuple[Any, ...] = ()
    per_query: Any = ()

    def __post_init__(self) -> None:
        if self.branches and (self.preferences or self.per_query):
            raise TypeError("an Intent takes preferences or branches, not both")
        if self.branches:
            object.__setattr__(self, "branches", tuple(_as_branch(b) for b in self.branches))
        object.__setattr__(self, "per_query", _per_query(self.per_query) if self.per_query else ())

    @property
    def plans(self) -> tuple[Branch, ...]:
        """The intent's branches, in order — one made of ``preferences`` and
        ``per_query`` without any."""
        return self.branches or (Branch(self.preferences, per_query=self.per_query),)


_PASS_PRIORITY = Intent(pattern=priority_pattern())


class EntryKind(Enum):
    ACT = "act"
    ILLEGAL = "act_illegal"
    PASS = "pass"


@dataclass(frozen=True)
class Branch:
    """One way to take a script entry's action.

    ``preferences`` choose the action, in order — the first preference any
    offered option satisfies wins, so ``(Decision.obj(printed=GleamOfDeath),
    Decision.obj(printed=GlamdringFoehammer))`` casts Gleam of Death, or casts
    Glamdring and then, when asked which face, Gleam of Death. While the action
    is being taken, ``preferences`` and then ``choices`` answer every query no
    card intent claims (targets, modes, X, payment).

    ``per_query`` pairs a key with the preferences that answer, instead, a
    query the key matches — so one branch can choose A for the question
    asking for an artifact and B for the one asking for a creature, on any
    query: priority, a declaration or a choice while casting or resolving. A
    key is an object the query's optional question payload holds
    (:func:`~engine.queries.asks_for`), such as ``CardType.ARTIFACT``, or a
    predicate over the query — its payload, options, source or bounds — to
    infer the question best-effort when the engine attaches no payload. Keys
    are tried in order and the first match wins. A query no key matches, such
    as one combined question for every type, is answered by the branch's own
    preferences, so the same branch fits every presentation.
    """

    preferences: tuple[PlayerDecision, ...] = ()
    choices: tuple[PlayerDecision, ...] = ()
    per_query: tuple[tuple[Any, tuple[PlayerDecision, ...]], ...] = ()

    def answers_for(self, query: PlayerQuery) -> tuple[PlayerDecision, ...]:
        """The preferences that answer ``query`` inside this branch's attempt."""
        return self._per_query(query) or self.preferences + self.choices

    def action_for(self, query: PlayerQuery) -> tuple[PlayerDecision, ...]:
        """The preferences that choose this branch's action in ``query``."""
        return self._per_query(query) or self.preferences

    def _per_query(self, query: PlayerQuery) -> tuple[PlayerDecision, ...]:
        for key, preferences in self.per_query:
            if _per_query_matches(key, query):
                return preferences
        return ()


def branch(
    *preferences: PlayerDecision | type,
    choices: tuple[PlayerDecision | type, ...] | list[PlayerDecision | type] = (),
    per_query: Mapping[Any, Any] | None = None,
) -> Branch:
    """A branch for :func:`act`, :func:`act_illegal` or an ``Intent`` with its
    own ``choices`` and ``per_query`` preferences, e.g.
    ``branch(A, B, per_query={CardType.ARTIFACT: [A], CardType.CREATURE: [B]})``."""
    return Branch(_decisions(preferences), _decisions(choices), _per_query(per_query))


def _as_branch(item: Any) -> Branch:
    return item if isinstance(item, Branch) else Branch(_decisions(item))


def _per_query_matches(key: Any, query: PlayerQuery) -> bool:
    """A predicate key is called with the query; any other key must be held
    by its question payload."""
    if callable(key) and not isinstance(key, type):
        return bool(key(query))
    return asks_for(query, key)


def _per_query(mapping: Any) -> tuple[tuple[Any, tuple[PlayerDecision, ...]], ...]:
    if isinstance(mapping, tuple):
        return mapping
    pairs = []
    for wanted, preferences in (mapping or {}).items():
        if isinstance(wanted, str):
            raise TypeError(f"a per_query key is a payload object or a predicate, not a string: {wanted!r}")
        values = preferences if isinstance(preferences, (list, tuple)) else (preferences,)
        pairs.append((wanted, _decisions(values)))
    return tuple(pairs)


@dataclass(frozen=True)
class ScriptEntry:
    """One priority action in a player's script.

    ``branches`` are tried in order: the first whose action is offered takes
    it, and each rejection of the action retries it with the next branch.
    ``goal`` is checked once the action has taken effect.
    """

    kind: EntryKind
    branches: tuple[Branch, ...] = (Branch(),)
    goal: Callable[[Any], bool] | None = None
    label: str = ""

    def describe(self) -> str:
        if self.label:
            return self.label
        return self.kind.value + " | ".join(_describe(b.preferences) for b in self.branches)


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
    branches: Any = None,
    per_query: Mapping[Any, Any] | None = None,
) -> ScriptEntry:
    """An action the player must take: it fails the test with
    :class:`ScriptEntryError` (a ``PostconditionError``) if no branch's action
    is offered, if the engine rejects it with ``InvalidPlayerChoiceError`` and
    no branch is left to retry it with, or if ``goal(game)`` is falsey once it
    has taken effect.

    ``preferences``, ``choices`` and ``per_query`` make one branch; ``branches``
    lists several instead, each a list of preferences or a :func:`branch`, with
    ``choices`` and ``per_query`` appended to every one. A rejected attempt is retried with the next branch
    and never otherwise: ``act(branches=[[GleamOfDeath, GlamdringFoehammer],
    [GlamdringFoehammer]])`` casts Glamdring when Gleam of Death is rejected,
    while ``act(GleamOfDeath, GlamdringFoehammer)`` fails.

    A preference may be a Player Decision or a predefined class: a card or
    face class stands for ``Decision.obj(printed=cls)``, an ability or mode
    class for ``Decision.ability(printed=cls)`` or ``Decision.mode(printed=cls)``.
    """
    return ScriptEntry(
        EntryKind.ACT, _branches(preferences, choices, branches, per_query), goal, label
    )


def act_illegal(
    *preferences: PlayerDecision | type,
    choices: tuple[PlayerDecision | type, ...] | list[PlayerDecision | type] = (),
    label: str = "",
    branches: Any = None,
    per_query: Mapping[Any, Any] | None = None,
) -> ScriptEntry:
    """An action the rules forbid: it passes if, for every branch in turn, no
    offered option satisfies the branch or the engine rejects it, and fails the
    test with :class:`ScriptEntryError` if any branch takes effect. Either way
    the entry is consumed, and the same Priority Query goes to the next entry.
    ``branches`` and ``per_query`` work as for :func:`act`."""
    return ScriptEntry(
        EntryKind.ILLEGAL, _branches(preferences, choices, branches, per_query), None, label
    )


def _branches(preferences: Any, choices: Any, branches: Any, per_query: Any) -> tuple[Branch, ...]:
    shared, shared_per_query = _decisions(choices), _per_query(per_query)
    if branches is None:
        return (Branch(_decisions(preferences), shared, shared_per_query),)
    if preferences:
        raise TypeError("a script entry takes preferences or branches, not both")
    if not branches:
        raise TypeError("a script entry needs at least one branch")
    return tuple(
        Branch(b.preferences, b.choices + shared, b.per_query + shared_per_query)
        if isinstance(b, Branch)
        else Branch(_decisions(b), shared, shared_per_query)
        for b in branches
    )


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
    """The script entry whose action is being taken, and the branch it is
    being taken with; each rejection the entry owns moves to the next one."""

    entry: ScriptEntry
    branch: int = 0
    error: InvalidPlayerChoiceError | None = None
    retrying: bool = False

    def ranked(self, query: PlayerQuery) -> list[tuple[int, PlayerDecision]]:
        return list(enumerate(self.entry.branches[self.branch].answers_for(query)))


_BASELINE_KEY = "<baseline>"
_ENTRY_KEY = "<script entry>"


class DeterministicPlayer(Player):
    """Intent-based deterministic player (V2). See module docstring.

    A Priority Query goes to a card intent whose pattern matches it (see
    :func:`~engine.queries.priority_pattern`); with none, it consumes the next
    script entry, and with a dry script the player passes — the Baseline Intent
    never takes an action, whatever its preferences.

    A rejected choice is retried only as the test spells it out (see ADR-017):
    the handler that owns the rejected answer — the script entry, or the routed
    intent that answered — retries the attempt with its next branch, and fails
    the test when it has none. Each branch answers every query of the attempt,
    so ``act(branches=[[GleamOfDeath, GlamdringFoehammer], [GlamdringFoehammer]])``
    falls back to Glamdring whether the engine offered Gleam of Death at once
    or asked for the face after the card, and a choice intent's next branch is
    tried while its entry's action is kept. A negative intent's choice that is
    rejected counts as a pass; one that takes effect fails. Script position and
    attempt bookkeeping are decision-side state, so a rollback leaves them
    alone (``rollback_exempt``).
    """

    rollback_exempt = frozenset({
        "_intents", "_baseline", "transcript", "game", "_script", "_attempt",
        "_forbidden_outside", "last_action_result",
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
        # Negative intents whose forbidden choice was accepted outside any attempt.
        self._forbidden_outside: set[str] = set()
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
            PostconditionError: if the intent's postcondition returns falsey,
                or a negative intent's forbidden choice took effect.
        """
        intent = self._intents.pop(name)
        if name in self._forbidden_outside:
            self._forbidden_outside.discard(name)
            raise PostconditionError(
                f"negative intent {name!r}: a forbidden choice took effect"
            )
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

    def on_attempt_rejected(
        self, context: Any, answer: AttemptAnswer, error: InvalidPlayerChoiceError
    ) -> str:
        if answer.key is None:
            # Answered outside this player's handlers (a subclass's own answer).
            return super().on_attempt_rejected(context, answer, error)
        if context.forbidden_by(answer):
            # A negative intent's choice was refused, as the rules require.
            return "pass"
        if answer.key == _ENTRY_KEY:
            return self._entry_rejected(context, answer, error)
        return self._choice_rejected(context, answer, error)

    def _entry_rejected(
        self, context: Any, answer: AttemptAnswer, error: InvalidPlayerChoiceError
    ) -> str:
        attempt = self._attempt
        if attempt is None:
            raise error
        attempt.error = error
        if attempt.branch + 1 < len(attempt.entry.branches):
            attempt.branch += 1
            attempt.retrying = True
            return "retry"
        self._attempt = None
        if attempt.entry.kind is EntryKind.ILLEGAL:
            # Rejected as it must be: the re-asked query goes to the next entry.
            return "retry"
        raise ScriptEntryError(attempt.entry, "rejected", error) from error

    def _choice_rejected(
        self, context: Any, answer: AttemptAnswer, error: InvalidPlayerChoiceError
    ) -> str:
        intent = self._baseline if answer.key == _BASELINE_KEY else self._intents.get(answer.key)
        handler = (id(self), answer.key)
        following = context.branch.get(handler, 0) + 1
        if intent is None or following >= len(intent.plans):
            if context.kind == "priority" and context.answers and context.answers[0] is answer:
                # A card intent chose this priority action and has no other.
                raise error
            raise PostconditionError(
                f"choice intent {answer.key!r} has no branch left after a rejection: {error}"
            ) from error
        context.branch[handler] = following
        return "retry"

    def settle_rejected_action(self, context: Any, error: InvalidPlayerChoiceError) -> bool:
        """Settle a rejection of the :func:`act_illegal` branch being taken:
        the rules refused it, as the entry expects, so the entry moves to its
        next branch, or hands the re-asked query to the next entry. A refused
        choice whose owner can still retry it with another branch is left to
        that owner, since the action may yet take effect."""
        attempt = self._attempt
        if attempt is None or attempt.entry.kind is not EntryKind.ILLEGAL:
            return False
        owner = context.owner(error)
        if owner is not None and owner.key != _ENTRY_KEY and owner.player.would_retry(context, owner):
            return False
        attempt.error = error
        if attempt.branch + 1 < len(attempt.entry.branches):
            attempt.branch += 1
            attempt.retrying = True
        else:
            self._attempt = None
        return True

    def would_retry(self, context: Any, answer: AttemptAnswer) -> bool:
        if answer.key is None or context.forbidden_by(answer):
            return False
        if answer.key == _ENTRY_KEY:
            attempt = self._attempt
            return attempt is not None and attempt.branch + 1 < len(attempt.entry.branches)
        intent = self._baseline if answer.key == _BASELINE_KEY else self._intents.get(answer.key)
        following = context.branch.get((id(self), answer.key), 0) + 1
        return intent is not None and following < len(intent.plans)

    def on_action_retried(self, context: Any) -> None:
        attempt = self._attempt
        if attempt is None:
            return
        # The entry's action and branch stay the same; only the choice inside
        # it is revised.
        attempt.retrying = True

    def on_action_ended(self, context: Any) -> None:
        # Whatever ended the action, its entry answers nothing after it.
        self._attempt = None

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
    # Answering
    # ------------------------------------------------------------------

    def answer(self, query: PlayerQuery) -> Answer:
        record = self.transcript._record(query)
        record.answer = self._answer(query, record)
        return record.answer

    def _answer(self, query: PlayerQuery, record: QueryRecord) -> Answer:
        claimed = self._card_intents_for(query)
        noted = attempts.current_answer(self)
        if is_priority_query(query):
            attempt = self._attempt
            if attempt is not None and attempt.retrying:
                attempt.retrying = False
                _note(noted, _ENTRY_KEY)
                answer = self._choose_action(attempt, query)
                if answer is not None:
                    return answer
            self._attempt = None
            if self._script and not claimed:
                _note(noted, _ENTRY_KEY)
                return self._answer_from_script(query)
        elif self._attempt is not None and not claimed:
            ranked = self._attempt.ranked(query)
            baseline_prefers = self._baseline is not None and _first_preferred(
                list(self._baseline.plans[0].answers_for(query)), query.options
            ) is not None
            if _first_preferred([p for _, p in ranked], query.options) is not None or (
                not baseline_prefers
            ):
                # Inside its action the entry answers every query nothing else
                # claims — by its branch, or by mandatory fill — so it owns
                # those answers when one of them is rejected.
                answer, _ = _select(ranked, query)
                _note(noted, _ENTRY_KEY)
                return answer

        name, intent = self._route(query, claimed)
        key = _BASELINE_KEY if name is None else name
        context = attempts.current()
        plans = intent.plans
        current = context.branch.get((id(self), key), 0) if context is not None else 0
        preferences = plans[min(current, len(plans) - 1)].answers_for(query)
        answer, used = _select(list(enumerate(preferences)), query)
        forbidden = intent.negative and bool(used)
        if noted is not None:
            _note(noted, key, forbidden)
        elif forbidden and name is not None:
            self._forbidden_outside.add(name)
        if name is not None and preferences and not used and query.min > 0:
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
            if answer is not None:
                return answer
        return Answer()

    def _choose_action(self, attempt: _EntryAttempt, query: PlayerQuery) -> Answer | None:
        """Choose ``attempt``'s action from a Priority Query with its current
        branch, skipping branches whose action is not offered. ``None`` means
        no branch is left; an :func:`act` then fails the test."""
        branches = attempt.entry.branches
        while attempt.branch < len(branches):
            for pref in branches[attempt.branch].action_for(query):
                for option in query.options:
                    if satisfies(option, pref):
                        self._attempt = attempt
                        return Answer(selected=(option,))
            attempt.branch += 1
        self._attempt = None
        if attempt.entry.kind is EntryKind.ACT:
            if attempt.error is not None:
                raise ScriptEntryError(attempt.entry, "rejected", attempt.error) from attempt.error
            raise ScriptEntryError(attempt.entry, "not offered")
        return None

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


def _note(noted: AttemptAnswer | None, key: str, forbidden: bool = False) -> None:
    """Record which handler gave the answer being given inside an attempt."""
    if noted is not None:
        noted.key, noted.forbidden = key, forbidden


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
