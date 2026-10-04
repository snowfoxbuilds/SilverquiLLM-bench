"""Attempted actions and choices: where a rejected choice is rolled back to,
and who decides whether it is tried again (see ADR-017).

An engine may let a player choose an illegal option as long as it rejects it
with :class:`~engine.decisions.InvalidPlayerChoiceError` and rolls the game
back to the start of the rejected action. Each attempt runs inside an
:class:`AttemptContext`, the one place that knows the rejection boundary, the
answers given during the attempt, and which answer owns a rejection:

* a **priority** action (:func:`engine.priority.take_priority`) starts at the
  beginning of its Priority Query, and a retry asks that query again;
* a **resolution** (:func:`resolve`, used by
  :func:`engine.stack.resolve_top_of_stack`) keeps every effect that came
  before its first choice: a retry replays it from the start with that state
  restored, and an abandoned attempt ends it at its first choice;
* an explicit **choice** attempt (:func:`attempt`) wraps one cast or choice
  that card code makes while resolving — such as one of several effect-granted
  casts — so a rejection reverses only that operation and the resolution
  continues after it, keeping what came before (CR 733).

A rejection belongs to one answer. A choice the card or engine refuses
(``InvalidPlayerChoiceError`` raised directly) belongs to the latest answer of
the attempt; an action the rules forbid as a whole (a casting, activation or
zone-move error) belongs to the answer that chose the action, the first one.
Only that answer's player hears the rejection, through
:meth:`~engine.player.Player.on_attempt_rejected`, and decides: ``"retry"``,
``"pass"`` (abandon the attempt, restored), or raise to fail.

A rejection its owner raises, or one with no answer to own it, is final: the
attempt has already restored its own boundary, so the error passes every
enclosing attempt without another rollback or notification — effects and casts
those attempts completed earlier stay in place — and the outermost attempt
re-raises it unchanged.

Before the owner hears a rejection in a priority action, the acting player may
settle it (:meth:`~engine.player.Player.settle_rejected_action`): an action its
script expected the rules to refuse is settled there, whoever answered the
refused choice.

An answer may also mark a *forbidden* choice — one a negative intent made on
purpose. If such an attempt takes effect, the attempt fails with
``PostconditionError``.

Contexts are decision-side bookkeeping, held outside the game, so a rollback
never touches them.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal

from engine.decisions import InvalidPlayerChoiceError, PostconditionError

Verdict = Literal["retry", "pass"]
AttemptKind = Literal["priority", "resolution", "choice"]


@dataclass(eq=False)
class AttemptAnswer:
    """One answer given during an attempt.

    ``key`` names the handler of the answering player that chose it, for the
    player to fill in. ``forbidden`` marks a choice a negative intent made on
    purpose.
    """

    player: Any
    key: Hashable | None = None
    forbidden: bool = False


@dataclass(eq=False)
class AttemptContext:
    """One attempted action or choice and every try at it."""

    game: Any
    kind: AttemptKind
    boundary: Any = None
    answers: list[AttemptAnswer] = field(default_factory=list)
    # The branch each handler answers this attempt's tries with, per
    # (id(player), handler key); a rejection the handler owns advances it.
    branch: dict[tuple[int, Hashable], int] = field(default_factory=dict)
    # The Priority Query and its answer, for a priority attempt.
    query: Any = None
    answer: Any = None
    # The answer that owned the latest rejection.
    owner_answer: AttemptAnswer | None = None
    # What runs outside the game during the attempt, snapshotted with it.
    roots: tuple[Any, ...] = ()

    def begin_try(self) -> None:
        self.boundary = None
        self.answers = []

    def before_query(self, player: Any) -> AttemptAnswer:
        """Note that ``player`` is being asked; the first query of a try is the
        rejection boundary of a resolution or priority attempt."""
        if self.boundary is None:
            from engine.rollback import take_snapshot

            self.boundary = take_snapshot(self.game, *self.roots)
        record = AttemptAnswer(player)
        self.answers.append(record)
        return record

    def owner(self, error: InvalidPlayerChoiceError) -> AttemptAnswer | None:
        if not self.answers:
            return None
        return self.answers[0] if _rejects_whole_action(error) else self.answers[-1]

    def reject(self, error: InvalidPlayerChoiceError) -> Verdict:
        """Let the owning answer's player decide what follows a rejection; a
        rejection it raises, or one nobody owns, is final (:class:`_Final`)."""
        owner = self.owner(error)
        if owner is None:
            raise _Final(error)
        self.owner_answer = owner
        try:
            return owner.player.on_attempt_rejected(self, owner, error)
        except InvalidPlayerChoiceError as refused:
            raise _Final(refused) from refused

    def forbidden_by(self, answer: AttemptAnswer) -> bool:
        """Whether ``answer``'s handler made a forbidden choice in this try."""
        return any(
            other.forbidden
            for other in self.answers
            if other.player is answer.player and other.key == answer.key
        )

    def check_forbidden(self) -> None:
        if any(a.forbidden for a in self.answers):
            raise PostconditionError(
                "a choice a negative intent forbids was allowed to take effect"
            )


_active: ContextVar[tuple[AttemptContext, ...]] = ContextVar("attempts", default=())


def current() -> AttemptContext | None:
    """The innermost attempt being made, if any."""
    stack = _active.get()
    return stack[-1] if stack else None


def current_answer(player: Any) -> AttemptAnswer | None:
    """The record of the answer ``player`` is giving right now, if inside an attempt."""
    context = current()
    if context is None or not context.answers or context.answers[-1].player is not player:
        return None
    return context.answers[-1]


class _Final(Exception):
    """A rejection no one retried or passed, on its way out of every attempt.

    It is not one of the errors that reject an action, so an enclosing attempt
    neither rolls back for it nor notifies anyone again; the outermost attempt
    re-raises the original ``error``.
    """

    def __init__(self, error: InvalidPlayerChoiceError) -> None:
        super().__init__(str(error))
        self.error = error


@contextmanager
def active(context: AttemptContext):
    outermost = not _active.get()
    token = _active.set((*_active.get(), context))
    try:
        yield context
    except _Final as final:
        if outermost:
            raise final.error from final.error.__cause__
        raise
    finally:
        _active.reset(token)


def resolve(game: Any, operation: Callable[[], Any], *roots: Any) -> bool:
    """Run a resolving object's effect as an attempt; return ``False`` if a
    rejected choice was abandoned, ending the resolution at that choice.
    ``roots`` — the popped StackObject — are rolled back with the game."""
    return _run(game, "resolution", operation, roots)[0]


def attempt(game: Any, operation: Callable[[], Any]) -> tuple[bool, Any]:
    """Run one cast or choice ``operation`` as its own attempt while an object
    resolves; return ``(True, result)``, or ``(False, None)`` if it was rejected
    and abandoned — rolled back, with everything before it kept."""
    return _run(game, "choice", operation, ())


def _run(
    game: Any, kind: AttemptKind, operation: Callable[[], Any], roots: tuple[Any, ...]
) -> tuple[bool, Any]:
    from engine.priority import REJECTED_ACTION_ERRORS, as_choice_error
    from engine.rollback import take_snapshot

    # The operation's own state (its closure) is part of what a retry restores.
    context = AttemptContext(game, kind, roots=(operation, *roots))
    start = take_snapshot(game, *context.roots)
    with active(context):
        while True:
            context.begin_try()
            if kind == "choice":
                context.boundary = start
            try:
                result = operation()
            except REJECTED_ACTION_ERRORS as exc:
                if kind == "resolution" and not isinstance(exc, InvalidPlayerChoiceError):
                    raise
                error = as_choice_error(exc)
                (context.boundary or start).restore()
                if context.reject(error) == "pass":
                    return False, None
                start.restore()
                continue
            context.check_forbidden()
            return True, result


def _rejects_whole_action(error: InvalidPlayerChoiceError) -> bool:
    from engine.priority import REJECTED_ACTION_ERRORS

    cause = error.__cause__
    return isinstance(cause, REJECTED_ACTION_ERRORS) and not isinstance(
        cause, InvalidPlayerChoiceError
    )
