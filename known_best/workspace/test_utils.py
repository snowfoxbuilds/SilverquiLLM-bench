"""Test utility helpers for engine validation and benchmark agents.

Provides convenience functions for setting up game states, casting spells,
advancing phases, and managing combat in tests.  Each function raises
descriptive errors on failure.

Play is driven through Priority Queries (ADR-017): a test gives each player an
ordered action script (:func:`script` with :func:`act`, :func:`act_illegal` and
:func:`pass_priority` entries) and drives it with :func:`run_scripts`; the
engine, not the test, performs each chosen cast, land play or activation. The
casting and activation helpers are one-entry scripts. A rejected action or
choice is retried only with the next of the test's explicit branches
(``act(branches=[...])``, ``Intent(branches=[...])``).

Functions:
    create_game — convenience wrapper to create a GameState from card lists.
    set_board_state — directly set zone contents and player state.
    script / run_scripts — give players action scripts and play them out.
    cast_spell — find card in hand by name, cast it through priority, and resolve.
    advance_to_phase — fast-forward game state to a given phase/step.
    declare_attackers — advance to combat and declare attackers by name.
    declare_blockers — declare blockers by name mapping.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, NoReturn

from engine import attempts
from engine.abilities import AbilityError
from engine.attempts import AttemptAnswer
from engine.card import CardImpl
from engine.casting import CastingError
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
from engine.game import create_game as _engine_create_game
from engine.game_state import _TURN_SEQUENCE, GameState, StepState
from engine.queries import (
    Answer,
    PlayerQuery,
    is_action_query,
    is_declaration_query,
    is_priority_query,
    priority_pattern,
)
from engine.stack import resolve_top_of_stack
from engine.state_based_actions import resolve_state_based_actions
from engine.turn import advance, start_step
from engine.types import ManaType, Phase, Step, Zone
from test_interface import Branch, ScriptedPlayer

# ---------------------------------------------------------------------------
# Intents and the intent-based DeterministicPlayer
# ---------------------------------------------------------------------------
#
# The Reference Tests' player, built on the Test Interface's ScriptedPlayer:
# the named ``Intent`` is the scoping/lifecycle layer, routing each query by
# its source refs, and answers come from preferences over Player Decisions —
# greedy, single pass, no search. A Baseline Intent handles system-level
# queries; a query matched by neither a card intent nor the baseline is an
# explicit failure.
#
# Priority actions are scripted (see ADR-017): each player holds an ordered
# script of action entries, and each Priority Query the player receives
# consumes the next one — :func:`act` (must take effect), :func:`act_illegal`
# (must not take effect) or :func:`pass_priority` — and answers every query
# raised while its action is being taken that no card intent claims. A dry
# script passes. What happens after a rejection is written by the test, never
# inferred: an entry or intent holds ordered branches, and the query the
# engine asks again after a rejection is answered with the next branch.


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
    answered differently: each branch is a preference list or a
    :func:`branch`, the first answers the attempt, and each rejection the
    intent owns answers the re-asked query with the next one. With
    ``preferences`` alone there is one branch, and its rejection fails the
    test (see ADR-017). ``per_query`` maps what a query asks for to the
    preferences that answer it, as in :func:`branch`.
    """

    pattern: GameRef
    preferences: tuple[PlayerDecision, ...] = ()
    postcondition: Callable[[Any], bool] | None = None
    branches: tuple[Any, ...] = ()
    per_query: Any = ()

    def __post_init__(self) -> None:
        if self.branches and self.preferences:
            raise TypeError("an Intent takes preferences or branches, not both")
        shared = _per_query(self.per_query) if self.per_query else ()
        object.__setattr__(self, "per_query", shared)
        if self.branches:
            # Like an entry's, a shared ``per_query`` follows each branch's own.
            object.__setattr__(self, "branches", tuple(
                replace(b, per_query=b.per_query + shared)
                for b in map(_as_branch, self.branches)
            ))

    @property
    def plans(self) -> tuple[Branch, ...]:
        """The intent's branches, in order — one made of ``preferences`` and
        ``per_query`` without any."""
        return self.branches or (Branch(self.preferences, per_query=self.per_query),)


# Declines a Priority Query (passing) or a combat declaration (declaring none).
_DECLINE = Intent(pattern=priority_pattern())


class EntryKind(Enum):
    ACT = "act"
    ILLEGAL = "act_illegal"
    PASS = "pass"


def branch(
    *preferences: PlayerDecision | type,
    choices: tuple[PlayerDecision | type, ...] | list[PlayerDecision | type] = (),
    per_query: Mapping[Any, Any] | None = None,
    distinct: bool = False,
    scoped: Mapping[Any, Any] | None = None,
) -> Branch:
    """A branch for :func:`act`, :func:`act_illegal` or an ``Intent`` with its
    own ``choices``, ``per_query`` preferences and ``scoped`` answers, e.g.
    ``branch(A, B, per_query={CardType.ARTIFACT: [A], CardType.CREATURE: [B]})``."""
    return Branch(
        _decisions(preferences), _decisions(choices), _per_query(per_query), distinct,
        _scoped(scoped),
    )


def _answers_for(plan: Branch, query: PlayerQuery) -> tuple[PlayerDecision, ...]:
    """The preferences that answer ``query`` inside ``plan``'s attempt."""
    matched = plan.matched(query)
    return plan.preferences + plan.choices if matched is None else matched


def _action_for(plan: Branch, query: PlayerQuery) -> tuple[PlayerDecision, ...]:
    """The preferences that choose ``plan``'s action in ``query``."""
    matched = plan.matched(query)
    return plan.preferences if matched is None else matched


def _as_branch(item: Any) -> Branch:
    return item if isinstance(item, Branch) else Branch(_decisions(item))


def _per_query(mapping: Any) -> tuple[tuple[Any, tuple[PlayerDecision, ...]], ...]:
    if isinstance(mapping, tuple):
        return mapping
    pairs = []
    for wanted, preferences in (mapping or {}).items():
        if isinstance(wanted, str) and not isinstance(wanted, Enum):
            raise TypeError(f"a per_query key is a payload object or a predicate, not a string: {wanted!r}")
        values = preferences if isinstance(preferences, (list, tuple)) else (preferences,)
        pairs.append((wanted, _decisions(values)))
    return tuple(pairs)


@dataclass(frozen=True)
class ScriptEntry:
    """One priority action in a player's script.

    ``branches`` are tried in order: the first whose action is offered takes
    it, and each rejection of the action answers the re-asked Priority Query
    with the next branch. ``goal`` is checked once the action has taken effect.
    """

    kind: EntryKind
    branches: tuple[Branch, ...] = (Branch(),)
    goal: Callable[[Any], bool] | None = None
    label: str = ""

    def describe(self) -> str:
        if self.label:
            return self.label
        return self.kind.value + " | ".join(_describe(b.preferences) for b in self.branches)


class ScopedChoiceUnavailable(InvalidPlayerChoiceError):
    """The player withdraws a branch whose scoped answer is not offered.

    The engine refused nothing — the branch's action is simply not on offer —
    but withdrawing it the way a rejection is handled rolls the attempt back
    before anything takes effect, and the re-asked query goes to the entry's
    next branch, or to the next entry for an :func:`act_illegal` with none.
    """


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
    scoped: Mapping[Any, Any] | None = None,
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

    For a combat declaration the preferences are the creatures declared, all
    of them; ``scoped`` maps a creature to what it attacks or blocks (a
    decision, a predefined class, or a list of them), e.g.
    ``act(wall, scoped={wall: bear})`` blocks the bear with the wall. Like
    ``choices``, ``scoped`` is appended to every branch.
    """
    return ScriptEntry(
        EntryKind.ACT, _branches(preferences, choices, branches, per_query, scoped), goal, label
    )


def act_illegal(
    *preferences: PlayerDecision | type,
    choices: tuple[PlayerDecision | type, ...] | list[PlayerDecision | type] = (),
    label: str = "",
    branches: Any = None,
    per_query: Mapping[Any, Any] | None = None,
    scoped: Mapping[Any, Any] | None = None,
) -> ScriptEntry:
    """An action the rules forbid: it passes if, for every branch in turn, no
    offered option satisfies the branch or the engine rejects it, and fails the
    test with :class:`ScriptEntryError` if any branch takes effect. Either way
    the entry is consumed, and the same Priority Query or declaration goes to
    the next entry. ``branches``, ``per_query`` and ``scoped`` work as for
    :func:`act`."""
    return ScriptEntry(
        EntryKind.ILLEGAL, _branches(preferences, choices, branches, per_query, scoped), None, label
    )


def _branches(
    preferences: Any, choices: Any, branches: Any, per_query: Any, scoped: Any
) -> tuple[Branch, ...]:
    shared, shared_per_query, shared_scoped = (
        _decisions(choices), _per_query(per_query), _scoped(scoped)
    )
    if branches is None:
        return (Branch(_decisions(preferences), shared, shared_per_query, scoped=shared_scoped),)
    if preferences:
        raise TypeError("a script entry takes preferences or branches, not both")
    if not branches:
        raise TypeError("a script entry needs at least one branch")
    return tuple(
        replace(
            b, choices=b.choices + shared, per_query=b.per_query + shared_per_query,
            scoped=b.scoped + shared_scoped,
        )
        if isinstance(b, Branch)
        else Branch(_decisions(b), shared, shared_per_query, scoped=shared_scoped)
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


def _scoped(
    scoped: Mapping[Any, Any] | None,
) -> tuple[tuple[tuple[PlayerDecision, ...], tuple[PlayerDecision, ...]], ...]:
    pairs = []
    for key, value in (scoped or {}).items():
        values = value if isinstance(value, (list, tuple)) else (value,)
        pairs.append((_decisions((key,)), _decisions(values)))
    return tuple(pairs)


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
    """The script entry whose action is being taken, the branch it is being
    taken with — each rejection the entry owns moves to the next one — and
    the priority attempt it is taken in, whose re-asked Priority Query it
    answers again."""

    entry: ScriptEntry
    branch: int = 0
    error: InvalidPlayerChoiceError | None = None
    context: Any = None
    # A combat declaration's preferences are a set, not alternatives.
    declaration: bool = False

    @property
    def current(self) -> Branch:
        return self.entry.branches[self.branch]


_BASELINE_KEY = "<baseline>"
_ENTRY_KEY = "<script entry>"


class DeterministicPlayer(ScriptedPlayer):
    """Intent-based deterministic player (V2). See module docstring.

    A Priority Query goes to a card intent whose pattern matches it (see
    :func:`~engine.queries.priority_pattern`); with none, it consumes the next
    script entry, and with a dry script the player passes — the Baseline Intent
    never takes an action, whatever its preferences.

    A rejected choice is answered again only as the test spells it out (see
    ADR-017): the engine asks the same query again, and the handler that owns
    the rejected answer — the script entry, or the routed intent that
    answered — answers it with its next branch, failing the test when it has
    none. Each branch answers every query of the attempt, so
    ``act(branches=[[GleamOfDeath, GlamdringFoehammer], [GlamdringFoehammer]])``
    falls back to Glamdring whether the engine offered Gleam of Death at once
    or asked for the face after the card, and a choice intent's next branch is
    tried while its entry's action is kept. Script position and attempt
    bookkeeping are decision-side state, so a rollback leaves them alone
    (``rollback_exempt``).
    """

    rollback_exempt = ScriptedPlayer.rollback_exempt | {
        "_intents", "_baseline", "transcript", "_script", "_attempt",
        "last_action_result",
    }

    def __init__(self, name: str, life: int = 20) -> None:
        super().__init__(name, life)
        self._intents: dict[str, Intent] = {}
        self._baseline: Intent | None = None
        self.transcript: Transcript = Transcript()
        # Set by the test harness so end_intent postconditions can read game.
        self.game: Any = None
        self._script: list[ScriptEntry] = []
        self._attempt: _EntryAttempt | None = None
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

    def on_attempt_rejected(
        self, context: Any, answer: AttemptAnswer, error: InvalidPlayerChoiceError
    ) -> None:
        if answer.key is None:
            # Answered outside this player's handlers (a subclass's own answer).
            super().on_attempt_rejected(context, answer, error)
        elif answer.key == _ENTRY_KEY:
            self._entry_rejected(error)
        else:
            self._choice_rejected(context, answer, error)

    def _entry_rejected(self, error: InvalidPlayerChoiceError) -> None:
        """The entry answers the re-asked Priority Query with its next branch;
        with none left, an :func:`act_illegal` entry has been refused as it
        must be and the query goes to the next entry, and an :func:`act`
        fails."""
        attempt = self._attempt
        if attempt is None:
            raise error
        attempt.error = error
        if attempt.branch + 1 < len(attempt.entry.branches):
            attempt.branch += 1
            return
        self._attempt = None
        if attempt.entry.kind is not EntryKind.ILLEGAL:
            raise ScriptEntryError(attempt.entry, "rejected", error) from error

    def _choice_rejected(
        self, context: Any, answer: AttemptAnswer, error: InvalidPlayerChoiceError
    ) -> None:
        intent = self._baseline if answer.key == _BASELINE_KEY else self._intents.get(answer.key)
        handler = (id(self), answer.key)
        following = context.branch.get(handler, 0) + 1
        if intent is not None and following < len(intent.plans):
            context.branch[handler] = following
            return
        if context.action_answer is answer:
            # A card intent chose this priority action and has no other.
            raise error
        attempt = self._attempt
        if (
            attempt is not None
            and attempt.entry.kind is EntryKind.ILLEGAL
            and context.actor is self
        ):
            # A choice inside an action the entry expects the rules to refuse
            # was refused: the entry moves on as if the action were.
            self._entry_rejected(error)
            return
        raise PostconditionError(
            f"choice intent {answer.key!r} has no branch left after a rejection: {error}"
        ) from error

    def on_action_ended(self, context: Any) -> None:
        # Whatever ended the action, its entry answers nothing after it.
        attempt, self._attempt = self._attempt, None
        if not context.taken:
            return
        self.last_action_result = context.result
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
        if is_action_query(query):
            attempt = self._attempt
            if attempt is not None and attempt.context is attempts.current():
                # The same Priority Query or declaration, asked again after a
                # rejection.
                _note(noted, _ENTRY_KEY)
                choose = self._choose_declaration if attempt.declaration else self._choose_action
                answer = choose(attempt, query)
                if answer is not None:
                    return answer
            self._attempt = None
            if self._script and not claimed:
                _note(noted, _ENTRY_KEY)
                return self._answer_from_script(query)
        elif self._attempt is not None and (
            pair := _scoped_pair(self._attempt.current, query)
        ) is not None:
            # The entry names this source explicitly, ahead of any card intent.
            _note(noted, _ENTRY_KEY)
            return self._answer_scoped(self._attempt, pair, query)
        elif self._attempt is not None and not claimed:
            current = self._attempt.current
            override = current.matched(query)  # evaluated once per decision
            preferences = current.preferences + current.choices if override is None else override
            if (
                override is not None
                or _first_preferred(list(preferences), query.options) is not None
                or not self._baseline_prefers(query)
            ):
                # Inside its action the entry answers every query nothing else
                # claims — by an explicit override, by its branch, or by
                # mandatory fill — so it owns those answers when one of them
                # is rejected.
                answer, _ = _select(list(enumerate(preferences)), query)
                _note(noted, _ENTRY_KEY)
                return answer

        if not claimed and self._baseline is None and 0 < len(query.options) <= query.min:
            # A forced choice — every offered option must be chosen — needs no
            # decision, such as an attacker whose only defender is the player.
            _note(noted, _BASELINE_KEY)
            if noted is not None:
                noted.forced = True
            return Answer(selected=query.options)

        name, intent = self._route(query, claimed)
        key = _BASELINE_KEY if name is None else name
        preferences = _answers_for(self._current_plan(key, intent), query)
        answer, used = _select(list(enumerate(preferences)), query)
        _note(noted, key)
        if name is not None and preferences and not used and query.min > 0:
            # A routed card intent answered purely by first-offered fill —
            # probable wrong option set or typo'd preference. Flagged in the
            # transcript so audits can catch it; not a hard failure.
            record.preference_miss = True
        return answer

    def _current_plan(self, key: str, intent: Intent) -> Branch:
        """The branch ``intent`` answers the current attempt with."""
        context = attempts.current()
        plans = intent.plans
        current = context.branch.get((id(self), key), 0) if context is not None else 0
        return plans[min(current, len(plans) - 1)]

    def _baseline_prefers(self, query: PlayerQuery) -> bool:
        """Whether the baseline's current branch prefers one of ``query``'s options."""
        if self._baseline is None:
            return False
        preferences = _answers_for(self._current_plan(_BASELINE_KEY, self._baseline), query)
        return _first_preferred(list(preferences), query.options) is not None

    def _answer_from_script(self, query: PlayerQuery) -> Answer:
        """Consume entries until one answers this Priority Query or declaration.

        An :func:`act_illegal` entry whose action is not offered is consumed
        and the query goes to the next entry; a dry script passes, or declares
        nothing.
        """
        declaration = is_declaration_query(query)
        context = attempts.current()
        while self._script:
            entry = self._script.pop(0)
            if context is not None:
                # A new entry is a new action: its choices start from their
                # first branches, whatever an earlier entry's retries reached.
                context.branch.clear()
            if entry.kind is EntryKind.PASS:
                return Answer()
            attempt = _EntryAttempt(entry, declaration=declaration)
            choose = self._choose_declaration if declaration else self._choose_action
            answer = choose(attempt, query)
            if answer is not None:
                return answer
        return Answer()

    def _choose_declaration(self, attempt: _EntryAttempt, query: PlayerQuery) -> Answer | None:
        """Choose every creature ``attempt``'s current branch names, skipping
        branches naming one that is not offered. ``None`` means no branch is
        left; an :func:`act` then fails the test."""
        branches = attempt.entry.branches
        while attempt.branch < len(branches):
            selected: list[PlayerDecision] = []
            remaining = list(query.options)
            for pref in _action_for(branches[attempt.branch], query):
                option = next((o for o in remaining if satisfies(o, pref)), None)
                if option is None:
                    break
                selected.append(option)
                remaining.remove(option)
            else:
                attempt.context = attempts.current()
                self._attempt = attempt
                return Answer(selected=tuple(selected))
            attempt.branch += 1
        return self._no_branch_left(attempt)

    def _choose_action(self, attempt: _EntryAttempt, query: PlayerQuery) -> Answer | None:
        """Choose ``attempt``'s action from a Priority Query with its current
        branch, skipping branches whose action is not offered. ``None`` means
        no branch is left; an :func:`act` then fails the test."""
        branches = attempt.entry.branches
        while attempt.branch < len(branches):
            for pref in _action_for(branches[attempt.branch], query):
                for option in query.options:
                    if satisfies(option, pref):
                        attempt.context = attempts.current()
                        self._attempt = attempt
                        return Answer(selected=(option,))
            attempt.branch += 1
        return self._no_branch_left(attempt)

    def _no_branch_left(self, attempt: _EntryAttempt) -> None:
        self._attempt = None
        if attempt.entry.kind is EntryKind.ACT:
            if attempt.error is not None:
                raise ScriptEntryError(attempt.entry, "rejected", attempt.error) from attempt.error
            raise ScriptEntryError(attempt.entry, "not offered")

    def _answer_scoped(self, attempt: _EntryAttempt, pair: int, query: PlayerQuery) -> Answer:
        """Answer with exactly the decisions of the current branch's ``scoped[pair]``."""
        _, values = attempt.current.scoped[pair]
        selected: list[PlayerDecision] = []
        remaining = list(query.options)
        for value in values:
            option = next((o for o in remaining if satisfies(o, value)), None)
            if option is None:
                break
            selected.append(option)
            remaining.remove(option)
        else:
            if query.min <= len(selected) <= query.max:
                return Answer(selected=tuple(selected))
        self._scoped_unavailable(attempt, f"its scoped answer to {query.prompt!r} is not offered")

    def _scoped_unavailable(self, attempt: _EntryAttempt, detail: str) -> NoReturn:
        """The branch's action, with its scoped answers, is not offered: an
        :func:`act` on its last branch fails; otherwise the branch is withdrawn
        before anything takes effect."""
        if attempt.entry.kind is EntryKind.ACT and attempt.branch + 1 >= len(attempt.entry.branches):
            self._attempt = None
            raise ScriptEntryError(attempt.entry, "not offered")
        raise ScopedChoiceUnavailable(f"{attempt.entry.describe()}: {detail}")

    def confirm_declaration(
        self, query: PlayerQuery, answer: Answer, outcome: tuple[Any, ...] = ()
    ) -> None:
        """Withdraw a scripted declaration whose outcome differs from its
        scoped answers — a declared creature attacking or blocking something
        other than what the branch names. Judged on the declaration that would
        take effect, never on which follow-up questions were asked: an engine
        may skip a question with only one possible answer (see ADR-017)."""
        attempt = self._attempt
        if attempt is None or not attempt.declaration:
            return
        for keys, values in attempt.current.scoped:
            for creature, targets in outcome:
                if any(satisfies(creature, key) for key in keys) and not _exactly(targets, values):
                    self._scoped_unavailable(
                        attempt, "a declared creature's declaration differs from its scoped answer"
                    )

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
        if is_action_query(query):
            return None, _DECLINE
        if self._baseline is not None:
            return None, self._baseline
        raise UnmatchedQueryError(
            f"no card intent and no baseline matched query {query.prompt!r}"
        )


def _exactly(targets: tuple[PlayerDecision, ...], values: tuple[PlayerDecision, ...]) -> bool:
    """Whether each of ``values`` is met by its own one of ``targets``, with none left over."""
    remaining = list(targets)
    for value in values:
        match = next((t for t in remaining if satisfies(t, value)), None)
        if match is None:
            return False
        remaining.remove(match)
    return not remaining


def _scoped_pair(current: Branch, query: PlayerQuery) -> int | None:
    """The index of the branch's ``scoped`` pair whose key matches a source of
    ``query``, if any."""
    for index, (keys, _) in enumerate(current.scoped):
        if any(satisfies(source, key) for source in query.source for key in keys):
            return index
    return None


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


def _note(noted: AttemptAnswer | None, key: str) -> None:
    """Record which handler gave the answer being given inside an attempt."""
    if noted is not None:
        noted.key = key


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


class TestSetupError(Exception):
    """Raised when a test utility function encounters an invalid setup."""


def card_colors(card: Any) -> set[str]:
    """Return a card's colors as single-letter strings, derived from its mana cost.

    Hybrid pips contribute both options. {C} and {X} contribute nothing.
    Returns an empty set for cards with no mana cost or only colorless/X pips.
    """
    colors: set[str] = set()
    cost = getattr(card, "mana_cost", None)
    if cost is None:
        return colors
    for mt in getattr(cost, "pips", {}):
        if mt != ManaType.COLORLESS:
            colors.add(mt.value)
    for hybrid in getattr(cost, "hybrid", []):
        if hybrid.option_a != ManaType.COLORLESS:
            colors.add(hybrid.option_a.value)
        if hybrid.option_b != ManaType.COLORLESS:
            colors.add(hybrid.option_b.value)
    return colors


# ---------------------------------------------------------------------------
# create_game
# ---------------------------------------------------------------------------


def create_game(
    deck1: list[CardImpl] | None = None,
    deck2: list[CardImpl] | None = None,
    *,
    player1_name: str = "Player1",
    player2_name: str = "Player2",
    player1_life: int = 20,
    player2_life: int = 20,
) -> GameState:
    """Create a new two-player game from card lists.

    This is a convenience wrapper around :func:`engine.game.create_game`
    that automatically creates intent-based :class:`DeterministicPlayer`
    instances. Choices are answered through Intents the test starts on the
    players (see :class:`Intent`), not a positional script.

    Parameters:
        deck1: Cards for player 1's deck.  Defaults to empty list.
        deck2: Cards for player 2's deck.  Defaults to empty list.
        player1_name: Display name for player 1.
        player2_name: Display name for player 2.
        player1_life: Starting life for player 1.
        player2_life: Starting life for player 2.

    Returns:
        A fully initialised :class:`GameState`.

    Raises:
        TestSetupError: If the inputs are invalid.
    """
    if deck1 is None:
        deck1 = []
    if deck2 is None:
        deck2 = []

    p1 = DeterministicPlayer(player1_name, life=player1_life)
    p2 = DeterministicPlayer(player2_name, life=player2_life)

    game = _engine_create_game(p1, p2, deck1, deck2)
    # Let end_intent postconditions read the game without an explicit arg.
    for player in game.players:
        player.game = game

    # When decks are empty (the convenience default), engine.game.create_game
    # attempts to draw 7 cards from each empty library, which sets the
    # drawn_from_empty_library loss flag.  Reset it for the convenience case.
    for player in game.players:
        if player.drawn_from_empty_library:
            player.drawn_from_empty_library = False

    # engine.game.create_game hardcodes life=20; restore custom values.
    if player1_life != 20:
        game.players[0].life = player1_life
    if player2_life != 20:
        game.players[1].life = player2_life

    return game


# ---------------------------------------------------------------------------
# set_board_state
# ---------------------------------------------------------------------------


def set_board_state(
    game: GameState,
    player_index: int,
    *,
    battlefield: list[Any] | None = None,
    hand: list[Any] | None = None,
    graveyard: list[Any] | None = None,
    life: int | None = None,
    mana: dict[ManaType, int] | None = None,
) -> None:
    """Directly set zone contents and player state for test setup.

    Replaces the contents of the specified zones (only zones that are
    explicitly provided are modified — others are left unchanged).

    For each card placed into a zone, ``owner`` and ``controller`` are
    set to the target player.

    Parameters:
        game: The game state to modify.
        player_index: Index of the player (0 or 1).
        battlefield: Cards/permanents to place on the battlefield.
        hand: Cards to place in hand.
        graveyard: Cards to place in graveyard.
        life: Life total to set (or ``None`` to leave unchanged).
        mana: Mana to add to the player's pool.  Keys are
            :class:`ManaType`, values are amounts.

    Raises:
        TestSetupError: If ``player_index`` is out of range.
    """
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has "
            f"{len(game.players)} players (indices 0–{len(game.players) - 1})"
        )

    player = game.players[player_index]

    if life is not None:
        player.life = life

    if mana is not None:
        player.mana_pool.empty()
        for mana_type, amount in mana.items():
            player.mana_pool.add(mana_type, amount)

    if battlefield is not None:
        _set_zone(game, player, Zone.BATTLEFIELD, battlefield)

    if hand is not None:
        _set_zone(game, player, Zone.HAND, hand)

    if graveyard is not None:
        _set_zone(game, player, Zone.GRAVEYARD, graveyard)


def _set_zone(
    game: GameState,
    player: Any,
    zone: Zone,
    cards: list[Any],
) -> None:
    """Replace a zone's contents with *cards*, assigning ownership.

    Each placed object is given a stable engine-minted ``instance_id`` (for the
    zone it is placed in) so a test can reference it in an Intent preference —
    e.g. ``Decision.obj(instance=bear.instance_id)``.
    """
    zone_container = player.zones[zone]
    # Clear existing contents
    for obj in zone_container.get_all():
        zone_container.remove(obj)

    # Add new contents
    for card in cards:
        card.owner = player
        card.controller = player
        zone_container.add(card)
        card.instance_id = game.refs.instance_id(card, zone.value)


# ---------------------------------------------------------------------------
# cast_spell
# ---------------------------------------------------------------------------


def cast_spell(
    game: GameState,
    player_index: int,
    card_name: str,
    targets: list[Any] | None = None,
) -> None:
    """Find a card in hand by name, cast it, and pass priority until resolved.

    The function:
    1. Locates the first card matching *card_name* in the player's hand.
    2. For a sorcery-speed spell, makes the caster the active player in a main
       phase (the current one, else precombat main); a changed phase or active
       player opens that main phase's window, so later drivers carry on from
       it.
    3. Casts it as a one-entry :func:`act` script: the player chooses the card
       in a Priority Query and the engine casts it.
    4. Passes priority for both players so the spell resolves.

    Parameters:
        game: The game state.
        player_index: Index of the casting player (0 or 1).
        card_name: Name of the card to find in hand.
        targets: Optional list of game objects/players to prefer for the
            target Player Query the engine raises during casting.  When
            provided, a transient Intent is started on the casting player
            that prefers each target by its engine-minted ``instance_id``
            (objects) or seat (players); the intent is ended after
            casting in a ``finally`` so it does not leak across calls.

    Raises:
        TestSetupError: If the card is not found in hand or casting fails.
    """
    if player_index < 0 or player_index >= len(game.players):
        raise TestSetupError(
            f"Invalid player_index {player_index} — game has {len(game.players)} players"
        )

    player = game.players[player_index]
    hand = game.get_hand(player)

    # Find the card by name
    card = None
    for obj in hand.get_all():
        if getattr(obj, "name", None) == card_name:
            card = obj
            break

    if card is None:
        hand_names = [getattr(c, "name", repr(c)) for c in hand.get_all()]
        raise TestSetupError(
            f"Card {card_name!r} not found in player {player_index}'s hand. "
            f"Hand contains: {hand_names}"
        )

    # Ensure sorcery-speed timing for non-instant spells
    from engine.types import CardType, Keyword

    is_instant = CardType.INSTANT in getattr(card, "card_types", set())
    has_flash = Keyword.FLASH in getattr(card, "keywords", Keyword(0))

    if not is_instant and not has_flash:
        _sorcery_timing(game, player_index, keep_main=True)

    # Ensure the stack is empty for sorcery-speed
    if not game.stack.is_empty():
        raise TestSetupError(f"Cannot cast {card_name!r} — stack is not empty")

    # Targets are chosen via a transient Intent: the engine raises a target
    # Player Query during casting; the intent prefers the given targets by their
    # engine-minted instance id (objects) or seat (players).
    intent_name: str | None = None
    if targets and isinstance(player, DeterministicPlayer):
        prefs = tuple(_target_preference(game, t) for t in targets)
        intent_name = f"_cast_{card_name}"
        player.start_intent(
            intent_name,
            Intent(
                pattern=GameRef(card=frozenset({("name", card_name)})),
                preferences=prefs,
            ),
        )

    try:
        _take_action(game, player, act(_hand_preference(game, card)))
    except ScriptEntryError as exc:
        reason = _rejection_cause(exc) or f"it is not offered at priority ({exc})"
        raise TestSetupError(f"Failed to cast {card_name!r}: {reason}") from exc
    except Exception as exc:
        raise TestSetupError(f"Failed to cast {card_name!r}: {exc}") from exc
    finally:
        if intent_name is not None and intent_name in player._intents:
            player.end_intent(intent_name)

    # Pass priority for both players to resolve the spell
    resolve_stack(game)


def _target_preference(game: GameState, target: Any) -> Any:
    """Build an Intent preference selecting *target* (a game object or player)."""
    seat = game.refs.seat_of(target)
    if seat is not None:
        return Decision.player(seat=seat)
    instance_id = getattr(target, "instance_id", None)
    if instance_id is None:
        # Best effort: mint for the battlefield (the common targeting zone).
        instance_id = game.refs.instance_id(target, "battlefield")
    return Decision.obj(instance=instance_id)


# ---------------------------------------------------------------------------
# Action scripts (ADR-017)
# ---------------------------------------------------------------------------


def script(game: GameState, player_index: int, *entries: ScriptEntry) -> None:
    """Give player ``player_index`` an ordered action script, replacing any
    entries left from an earlier one.

    Each Priority Query the player receives consumes the next entry:
    :func:`act` (an action that must take effect), :func:`act_illegal` (one the
    rules forbid) or :func:`pass_priority`. Preferences name predefined classes
    or Player Decisions, e.g. ``act(GleamOfDeath, GlamdringFoehammer)`` or
    ``act(Decision.ability(printed=LlanowarElvesAbility1))``.
    """
    _deterministic(game, game.players[player_index]).set_script(entries)


def run_scripts(game: GameState, *, max_priority: int = 1000) -> None:
    """Play until every player's script is consumed or the game ends, leaving
    the stack in place.

    Play goes through the engine's one step lifecycle
    (:func:`~engine.turn.advance`): priority moves as in a real game — a player
    who acts keeps priority, every player passing in succession resolves the
    top of the stack (the active player then receives priority) or, on an
    empty stack, ends the step. A player whose script is dry passes.

    The priority round is the open window's own, so a later call carries on
    from where the scripts ran out.

    A rejected choice is rolled back and the same query asked again (see
    :mod:`engine.attempts`): within a priority action, the entry or intent that
    owns the rejection answers it with its next branch; while an object
    resolves, the owning intent does.

    Raises:
        ScriptEntryError: When an entry's action does not go as it requires.
        PostconditionError: When a rejected choice's intent has no branch left.
        TestSetupError: If the scripts are not consumed within ``max_priority``
            grants of priority.
    """
    grants = 0
    while _scripts_remain(game) and not game.is_game_over:
        window = game.window
        if window is not None and not window.all_passed(len(game.players)):
            if grants == max_priority:
                raise TestSetupError(f"scripts not consumed within {max_priority} grants of priority")
            grants += 1
        advance(game)


def _scripts_remain(game: GameState) -> bool:
    return any(isinstance(p, DeterministicPlayer) and p.pending_entries for p in game.players)


def _deterministic(game: GameState, player: Any) -> DeterministicPlayer:
    if not isinstance(player, DeterministicPlayer):
        raise TestSetupError(f"{player!r} is not a DeterministicPlayer and has no action script")
    return player


def _sorcery_timing(game: GameState, seat: int, *, keep_main: bool) -> None:
    """Make *seat* the active player in a main phase, for a casting wrapper's
    sorcery-speed cast: precombat main, or the current main phase when
    ``keep_main``. A changed phase, step or active player starts that main
    phase with its window open (:func:`~engine.turn.start_step`), so every
    driver carries on from it."""
    main = game.phase in (Phase.PRECOMBAT_MAIN, Phase.POSTCOMBAT_MAIN)
    phase = game.phase if keep_main and main else Phase.PRECOMBAT_MAIN
    if (game.phase, game.step, game.active_player_index) != (phase, None, seat):
        game.phase, game.step, game.active_player_index = phase, None, seat
        start_step(game)


def _take_action(game: GameState, player: Any, entry: ScriptEntry) -> Any:
    """Give *player* priority once with *entry* as their whole script; return
    what the engine's action returned. Their own script is left untouched.

    A player acts only in an open priority window: when the current step's
    window is not open — its actions still pending, or the step complete —
    it is opened first, so every driver afterwards carries on from that
    window rather than past the action."""
    from engine.priority import take_priority

    player = _deterministic(game, player)
    if game.step_state is not StepState.WINDOW:
        game.open_window()
    game.priority_player_index = game.players.index(player)
    saved = player.set_script([entry])
    player.last_action_result = None
    try:
        if not take_priority(game, player):
            game.window.acted()
    finally:
        player.set_script(saved)
    return player.last_action_result


def _rejection_cause(error: ScriptEntryError) -> BaseException | None:
    """The engine error behind a rejected entry, if it was rejected."""
    if error.error is None:
        return None
    return error.error.__cause__ or error.error


def _hand_preference(game: GameState, card: Any) -> Any:
    return Decision.obj(instance=game.refs.instance_id(card, Zone.HAND.value))


def _ability_preference(game: GameState, source: Any, index: int) -> Any:
    return Decision.ability(
        source=game.refs.instance_id(source, Zone.BATTLEFIELD.value), index=index
    )


def _activate(game: GameState, player: Any, source: Any, index: int) -> Any:
    try:
        return _take_action(game, player, act(_ability_preference(game, source, index)))
    except ScriptEntryError as exc:
        cause = _rejection_cause(exc)
        if cause is not None:
            raise cause
        raise AbilityError(
            f"{getattr(source, 'name', source)!r} ability {index} cannot be activated now"
        ) from exc


def _cast(game: GameState, player: Any, card: Any) -> Any:
    try:
        return _take_action(game, player, act(_hand_preference(game, card)))
    except ScriptEntryError as exc:
        cause = _rejection_cause(exc)
        if cause is not None:
            raise cause
        raise CastingError(f"{getattr(card, 'name', card)!r} cannot be cast now") from exc


def put_on_battlefield(game: GameState, player: Any, card: Any) -> Any:
    """Place a single *card* on *player*'s battlefield; return it.

    The card is given a stable engine-minted ``instance_id`` so a test can
    reference it in an Intent preference (``Decision.obj(instance=card.instance_id)``).
    """
    bf = player.zones[Zone.BATTLEFIELD]
    card.owner = player
    card.controller = player
    bf.add(card)
    card.instance_id = game.refs.instance_id(card, Zone.BATTLEFIELD.value)
    return card


def resolve_stack(game: GameState) -> None:
    """Resolve the entire stack with every player passing; consumes no script
    entries.

    Each resolution is the engine's own (:func:`~engine.stack.resolve_top_of_stack`):
    a choice the engine rejects while an object resolves is rolled back and
    asked again, answered with the owning intent's next branch. In an open
    window the active player then holds priority.

    In a cleanup step the cleanup step is then finished too, with every
    player passing (:func:`finish_cleanup`): another cleanup follows the
    window, and so on until one opens no window (CR 514.3a).
    """
    _drain_stack(game)
    if _in_cleanup(game):
        _finish_cleanup(game)


def _drain_stack(game: GameState) -> None:
    """Resolve the stack with every player passing (the open window's
    all-pass policy), or object by object when a test left objects on the
    stack outside any window. The game settles first, as it does before a
    player would receive priority, so abilities that triggered since are on
    the stack (rule 117.5)."""
    resolve_state_based_actions(game)
    while not game.stack.is_empty() and not game.is_game_over:
        if game.step_state is StepState.WINDOW:
            advance(game, all_pass=True)
        else:
            resolve_top_of_stack(game)


def card_abilities(card: Any) -> list:
    """``card``'s activated abilities, followed by any mana abilities it lists
    only in ``get_mana_abilities()``, so either placement of a mana ability
    can be activated by index."""
    abilities = list(card.get_activated_abilities())
    mana = getattr(card, "get_mana_abilities", lambda: [])()
    return abilities + [ability for ability in mana if not any(ability is a for a in abilities)]


def activate_card_ability(
    game: GameState,
    player: Any,
    source_card: Any,
    index: int = 0,
) -> None:
    """Activate ability ``index`` of :func:`card_abilities` (``source_card``'s
    activated abilities, then its other mana abilities) as a one-entry
    :func:`act` script: *player* chooses the ability in a Priority Query and
    the engine activates it — choosing targets **before** paying costs and
    putting it on the stack (a mana ability resolves at once). The caller
    resolves the stack afterward (e.g. via :func:`resolve_stack`) to run the
    ability's effect.

    Raises :class:`~engine.abilities.AbilityError` when the ability is not
    offered or the engine rejects it (no legal target, unmet timing, or
    unpayable cost) — the rejected activation is rolled back, so no cost is
    spent.
    """
    _activate(game, player, source_card, index)


def activate_loyalty_ability(
    game: GameState,
    player: Any,
    source_card: Any,
    index: int = 0,
) -> None:
    """Activate ``source_card``'s loyalty ability ``index`` as a one-entry
    :func:`act` script: *player* chooses it in a Priority Query (offered only
    at sorcery speed and once per turn) and the engine activates it, choosing
    targets **before** paying the loyalty cost. The caller resolves the stack
    afterward (e.g. via :func:`resolve_stack`) to run the ability's effect.

    Raises :class:`~engine.abilities.AbilityError` when the ability is not
    offered or the engine rejects it (wrong timing, already activated this
    turn, insufficient loyalty, or a required target with no legal choice) —
    no loyalty is spent in that case.
    """
    from engine.priority import activatable_abilities

    loyalty_offset = len(activatable_abilities(source_card, game)) - len(
        source_card.get_loyalty_abilities()
    )
    _activate(game, player, source_card, loyalty_offset + index)


# ---------------------------------------------------------------------------
# advance_to_phase
# ---------------------------------------------------------------------------


def advance_to_phase(
    game: GameState,
    phase: Phase,
    step: Step | None = None,
) -> None:
    """Fast-forward the game state to the specified phase/step.

    Advances by calling :meth:`GameState.advance_phase` until the target
    phase (and optionally step) is reached.  Priority is not granted during
    fast-forwarding — this is a direct state manipulation for test setup.

    Parameters:
        game: The game state to advance.
        phase: The target phase.
        step: The target step (or ``None`` for main phases).

    Raises:
        TestSetupError: If the target phase/step is not found within
            a full turn cycle (prevents infinite loops).
    """
    target = (phase, step)

    # Validate that (phase, step) is a valid combination
    valid_targets = {(p, s) for p, s in _TURN_SEQUENCE}
    if target not in valid_targets:
        raise TestSetupError(
            f"Invalid phase/step combination: ({phase!r}, {step!r}). "
            f"Valid combinations: {sorted(valid_targets, key=lambda x: str(x))}"
        )

    # Already there?
    if (game.phase, game.step) == target:
        return

    # Advance up to a full turn's worth of steps to prevent infinite loops
    max_advances = len(_TURN_SEQUENCE) + 1
    for _ in range(max_advances):
        game.advance_phase()
        if (game.phase, game.step) == target:
            # Setup only: the step counts as entered without its actions.
            start_step(game)
            return

    raise TestSetupError(
        f"Could not reach phase/step ({phase!r}, {step!r}) within "
        f"a full turn cycle. Current: ({game.phase!r}, {game.step!r})"
    )


# ---------------------------------------------------------------------------
# declare_attackers
# ---------------------------------------------------------------------------


def declare_attackers(
    game: GameState,
    attacker_names: list[Any],
    *,
    illegal: bool = False,
) -> None:
    """Advance to combat and declare attackers.

    1. Advances to the Declare Attackers step if not already there.
    2. Finds the creatures on the active player's battlefield matching the
       given names (a creature object may be given instead of a name).
    3. Declares exactly those attackers as a one-entry :func:`act` script: the
       engine asks the active player which creatures attack — and what each
       attacks, which this helper answers with the defending player — and
       registers them.

    With ``illegal=True`` the declaration is one the rules forbid, scripted as
    :func:`act_illegal`: the engine may decline to offer it or reject it, and
    then no attackers are declared.

    Parameters:
        game: The game state.
        attacker_names: Names of creatures to declare as attackers.
        illegal: Whether the declaration is expected to be illegal.

    Raises:
        TestSetupError: If any named creature is not found on the
            active player's battlefield.
        ScriptEntryError: If the engine does not offer a named creature or
            rejects the declaration (a creature that can't attack) — or, with
            ``illegal=True``, if it lets the declaration take effect.
    """
    from engine.combat import declare_attackers_step

    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_ATTACKERS):
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_ATTACKERS)

    active = game.active_player
    attackers = _battlefield_objects(
        game, active, attacker_names, "Attacker", "active", listing="Battlefield contains"
    )
    defending_seat = game.refs.seat_of(game.non_active_player)
    entry = (act_illegal if illegal else act)(
        *(_battlefield_preference(game, a) for a in attackers),
        choices=(Decision.player(seat=defending_seat),),
    )
    _declare(game, active, entry, declare_attackers_step)


# ---------------------------------------------------------------------------
# declare_blockers
# ---------------------------------------------------------------------------


def declare_blockers(
    game: GameState,
    assignments: dict[Any, list[Any]],
    *,
    illegal: bool = False,
) -> None:
    """Declare blockers by name mapping.

    The blocks are declared as a one-entry :func:`act` script: the engine asks
    the defending player which creatures block and then what each blocks, and
    registers them. When an attacker is multi-blocked the engine raises a
    damage-order Player Query to the attacker's controller — set a Baseline
    Intent on that player if so.

    With ``illegal=True`` the blocks are ones the rules forbid, scripted as
    :func:`act_illegal`: the engine may decline to offer them or reject them,
    and then no blockers are declared.

    Parameters:
        game: The game state.
        assignments: A mapping of ``{"attacker_name": ["blocker_name", ...]}``.
            Each attacker on the active player's battlefield is matched by
            name, and each blocker on the defending player's battlefield is
            matched by name (creature objects may be given instead of names).
        illegal: Whether the declaration is expected to be illegal.

    Raises:
        TestSetupError: If any named creature is not found.
        ScriptEntryError: If the engine does not offer a named blocker or
            rejects the declaration (evasion, menace, "can't block") — or,
            with ``illegal=True``, if it lets the declaration take effect.
    """
    from engine.combat import declare_blockers_step

    if (game.phase, game.step) != (Phase.COMBAT, Step.DECLARE_BLOCKERS):
        advance_to_phase(game, Phase.COMBAT, Step.DECLARE_BLOCKERS)

    active = game.active_player
    defending = game.non_active_player

    # Each blocker once, with every attacker it is to block: a creature given
    # under several attackers multi-blocks, and the engine judges whether it may.
    blocks: dict[Any, list[Any]] = {}
    for attacker_name, blocker_names in assignments.items():
        (attacker,) = _battlefield_objects(game, active, [attacker_name], "Attacker", "active")
        for blocker in _battlefield_objects(
            game, defending, blocker_names, "Blocker", "defending", exclude=blocks
        ):
            blocked = blocks.setdefault(blocker, [])
            if attacker not in blocked:
                blocked.append(attacker)

    entry = (act_illegal if illegal else act)(
        *(_battlefield_preference(game, b) for b in blocks),
        scoped={
            _battlefield_preference(game, b): [_battlefield_preference(game, a) for a in attackers]
            for b, attackers in blocks.items()
        },
    )
    _declare(game, defending, entry, declare_blockers_step)


def _battlefield_objects(
    game: GameState,
    player: Any,
    names: list[Any],
    role: str,
    side: str,
    exclude: Any = (),
    listing: str = "Available",
) -> list[Any]:
    """The creatures on *player*'s battlefield named by *names*, each found
    once (a creature object stands for itself). A name prefers a creature not
    in *exclude*, and otherwise falls back to one that is — so a blocker named
    under two attackers is one blocker blocking both when there is only one."""
    objects = game.get_battlefield(player).get_all()
    found: list[Any] = []
    for name in names:
        if not isinstance(name, str):
            found.append(name)
            continue
        named = [obj for obj in objects if getattr(obj, "name", None) == name and obj not in found]
        match = next((obj for obj in named if obj not in exclude), named[0] if named else None)
        if match is None:
            raise TestSetupError(
                f"{role} {name!r} not found on {side} player's battlefield. "
                f"{listing}: {[getattr(c, 'name', repr(c)) for c in objects]}"
            )
        found.append(match)
    return found


def _battlefield_preference(game: GameState, obj: Any) -> Any:
    return Decision.obj(instance=game.refs.instance_id(obj, Zone.BATTLEFIELD.value))


def _declare(game: GameState, player: Any, entry: ScriptEntry, step: Any) -> None:
    """Run combat declaration *step* with *entry* as *player*'s whole script;
    their own script is left untouched.

    The declaration is the step's turn-based action, so it goes through the
    step lifecycle: a step whose actions are pending is entered (declaring
    once and opening its window); one already marked entered by setup
    declares now and keeps, or opens, its window — so no driver declares
    again afterwards."""
    player = _deterministic(game, player)
    saved = player.set_script([entry])
    try:
        if game.step_state is StepState.PENDING:
            advance(game)
        else:
            step(game)
            if game.step_state is not StepState.WINDOW:
                game.open_window()
        unconsumed = player.pending_entries
    finally:
        player.set_script(saved)
    if unconsumed and entry.kind is EntryKind.ACT and any(map(_declares, entry.branches)):
        # The step raised no declaration (blockers with nothing attacking),
        # yet a branch named creatures to declare.
        raise ScriptEntryError(entry, "not offered")


def _declares(branch: Any) -> bool:
    """Whether *branch* names any creature to declare; one naming none
    declares nothing, which a step raising no declaration fulfils."""
    return bool(branch.preferences) or any(prefs for _, prefs in branch.per_query)


def enter_permanent(game, player, card):
    """Set up a hand card, then enter through the canonical zone-transition pipeline."""
    from engine.zones import move_to_zone

    card.owner = player
    card.controller = player
    game.get_hand(player).add(card)
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)
    return card


def advance_game_to_phase(game, phase, step=None):
    """Drive canonical phase transitions and their public boundary events.

    Consumes no script entries: play goes through the engine's step lifecycle
    with every player passing and the forced fast-forward
    (:func:`~engine.turn.advance`). Arriving at the target step performs its
    turn-based actions and returns with its window open and the game settled
    as it is before a player receives priority, so what the step's start
    triggered is on the stack (rule 117.5) — except cleanup, which as the
    target is completed (:func:`finish_cleanup`).
    """
    first = True
    start_turn = game.turn_number
    while game.turn_number <= start_turn + 2:
        if game.is_game_over:
            return
        at_target = (game.phase, game.step) == (phase, step)
        if at_target and _in_cleanup(game):
            _finish_cleanup(game)
            return
        if at_target and (first or game.step_state is not StepState.PENDING):
            if game.step_state is StepState.WINDOW:
                resolve_state_based_actions(game)
            return
        first = False
        advance(game, all_pass=True, forced=True)
    raise TestSetupError("phase boundary was not reached")


def behavioral_game():
    from engine.card import Creature

    game = create_game()
    game.phase, game.step = Phase.PRECOMBAT_MAIN, None
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
        for i in range(40):
            game.get_library(player).add(
                Creature(name=f"Library {i}", owner=player, base_power=2, base_toughness=2)
            )
    return game


def prefer(player, *decisions):
    player.set_baseline(Intent(pattern=GameRef(), preferences=tuple(decisions)))


def object_preference(game, card):
    from engine.stack import object_current_zone

    zone = object_current_zone(game, card)
    if zone is None:
        raise TestSetupError("Choice object has not been placed in a zone")
    return Decision.obj(instance=game.refs.instance_id(card, zone))


def cast_vanilla_spell(game, seat, value=2):
    from engine.card import Instant
    from engine.types import ManaCost

    spell = Instant(
        name=f"Test spell {value}", owner=game.players[seat], mana_cost=ManaCost(generic=value)
    )
    game.get_hand(game.players[seat]).add(spell)
    game.players[seat].mana_pool.add(ManaType.COLORLESS, value)
    return _cast(game, game.players[seat], spell)


def ability_instance(game, player, source, index=0):
    """Prepare a reusable activation through the canonical public descriptor types."""
    from engine.abilities import ActivatedAbilityInstance
    from engine.card import ManaAbility

    descriptor = card_abilities(source)[index]
    is_mana = isinstance(descriptor, ManaAbility)
    return ActivatedAbilityInstance(
        source=source,
        controller=player,
        cost=descriptor.cost,
        effect=descriptor.mana_produced if is_mana else descriptor.effect,
        is_mana_ability=is_mana,
        description=descriptor.description,
        targeting=getattr(descriptor, "targeting", None),
        can_activate=getattr(descriptor, "can_activate", None),
    )


def cast_card(game, player, card, resolve=True):
    """Stage an unzoned card and cast it as a one-entry :func:`act` script; the
    test supplies mana and Intents. Returns what the engine's cast returned.

    A sorcery-speed card is cast by its caster as the active player in
    precombat main; moving there opens that main phase's window, so later
    drivers carry on from it.

    Raises :class:`~engine.casting.CastingError` when the card is not offered
    at priority or the engine rejects the cast (rolled back).
    """
    from engine.casting import can_cast_at_instant_speed
    from engine.stack import object_current_zone

    if card.owner is None:
        card.owner = player
    card.controller = player
    zone = object_current_zone(game, card)
    if zone is None:
        game.get_hand(player).add(card)
    elif not game.get_hand(player).contains(card):
        raise TestSetupError("cast_card expects an unzoned card or one in the caster's hand")
    if not can_cast_at_instant_speed(card):
        _sorcery_timing(game, game.players.index(player), keep_main=False)
    result = _cast(game, player, card)
    if resolve:
        resolve_stack(game)
    return result


def finish_cleanup(game):
    """Complete the current cleanup step with every player passing; consumes
    no entries.

    It carries on from the step state: an open window's stack is resolved
    and the window closed, then cleanup steps follow until one opens no
    window (CR 514.3a); a completed cleanup is left alone.

    Raises:
        TestSetupError: Outside a cleanup step.
    """
    if not _in_cleanup(game):
        raise TestSetupError("finish_cleanup called outside a cleanup step")
    _finish_cleanup(game)


def _in_cleanup(game: GameState) -> bool:
    return (game.phase, game.step) == (Phase.ENDING, Step.CLEANUP)


def _finish_cleanup(game: GameState) -> None:
    """Advance the current cleanup step to DONE with every player passing."""
    while game.step_state is not StepState.DONE and not game.is_game_over:
        advance(game, all_pass=True, forced=True)


def scenario_game(*args, **kwargs):
    """Create an empty canonical game with deterministic first-offered defaults."""
    game = create_game(*args, **kwargs)
    for player in game.players:
        player.set_baseline(Intent(pattern=GameRef()))
    return game


def fund_mana_cost(player, cost):
    """Provide a specified cost's mana as test setup, without paying it."""
    for color, amount in cost.pips.items():
        player.mana_pool.add(color, amount)
    player.mana_pool.add(ManaType.COLORLESS, cost.generic)


def mana_ability_instance(game, player, source, index=0):
    from engine.abilities import ActivatedAbilityInstance

    descriptor = source.get_mana_abilities()[index]
    return ActivatedAbilityInstance(
        source=source,
        controller=player,
        cost=descriptor.cost,
        effect=descriptor.mana_produced,
        is_mana_ability=True,
        description=descriptor.description,
    )
