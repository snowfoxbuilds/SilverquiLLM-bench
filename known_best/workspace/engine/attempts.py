"""Attempted actions and choices: where a rejected choice is rolled back to,
and who hears the rejection (see ADR-017).

An engine may let a player choose an illegal option as long as it rejects it
with :class:`~engine.decisions.InvalidPlayerChoiceError` and rolls the game
back to the start of the rejected action. Each attempt runs inside an
:class:`AttemptContext`, the one place that knows the rejection boundary, the
answers given during the attempt, and which answer owns a rejection:

* a **priority** action (:func:`engine.priority.take_priority`) starts at the
  beginning of its Priority Query;
* a combat **declaration** (:mod:`engine.combat`) starts at the beginning of
  the declaration, and a rejection belongs to the declaring answer, since a
  declaration is legal or illegal as a whole;
* a **resolution** (:func:`resolve`, used by
  :func:`engine.stack.resolve_top_of_stack`) keeps every effect that came
  before its first choice, and runs again from there;
* an explicit **choice** attempt (:func:`attempt`) wraps one cast or choice
  that card code makes while resolving — such as one of several effect-granted
  casts — so a rejection reverses only that operation, keeping what the
  resolution did before it (CR 733).

Every rejection is rolled back to its boundary and the same query is asked
again (CR 733.2): nothing is passed, ended or skipped on a player's behalf.
The owner of the rejection answers the re-asked query differently — another
action, another choice, or declining where that is legal — or raises.

A rejection belongs to one answer that made a decision; an answer to a query
that offered only one possible answer is ``forced`` and owns one only when no
answer of the attempt made a decision. A choice the card or engine refuses
(``InvalidPlayerChoiceError`` raised directly) belongs to the latest answer of
the attempt; an action the rules forbid as a whole (a casting, activation or
zone-move error) belongs to the answer that chose the action, the first one.
Only that answer's player hears the rejection, through
:meth:`~engine.player.Player.on_attempt_rejected`, which returns to let the
query be asked again or raises to fail.

A rejection its owner raises, or one with no answer to own it, is final: the
attempt has already restored its own boundary, so the error passes every
enclosing attempt without another rollback or notification — effects and casts
those attempts completed earlier stay in place — and the outermost attempt
re-raises it unchanged.

Contexts are decision-side bookkeeping, held outside the game, so a rollback
never touches them.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal

from engine.decisions import InvalidPlayerChoiceError

AttemptKind = Literal["priority", "declaration", "resolution", "choice"]


@dataclass(eq=False)
class AttemptAnswer:
    """One answer given during an attempt.

    ``key`` names the handler of the answering player that chose it, for the
    player to fill in.
    """

    player: Any
    key: Hashable | None = None
    # The query offered only one possible answer, so no decision was made
    # and the answer owns a rejection only when no other answer does.
    forced: bool = False


@dataclass(eq=False)
class AttemptContext:
    """One attempted action or choice and every try at it.

    ``actor`` is the player whose action the attempt belongs to: the player
    with priority, a resolving object's controller, or, for a choice attempt,
    the actor of the attempt it is made in. ``action`` is that action: the
    Priority Query's chosen option, the resolving object, or the enclosing
    attempt's action.
    """

    game: Any
    kind: AttemptKind
    actor: Any = None
    action: Any = None
    boundary: Any = None
    answers: list[AttemptAnswer] = field(default_factory=list)
    # The branch each handler answers this attempt's tries with, per
    # (id(player), handler key); a rejection the handler owns advances it.
    branch: dict[tuple[int, Hashable], int] = field(default_factory=dict)
    # The Priority Query or declaration and its latest answer, and
    # whether the chosen action took effect, with what the engine returned.
    query: Any = None
    answer: Any = None
    taken: bool = False
    result: Any = None
    # What runs outside the game during the attempt, snapshotted with it.
    roots: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        enclosing = current()
        if self.kind == "choice" and enclosing is not None:
            self.actor, self.action = enclosing.actor, enclosing.action

    def begin_try(self) -> None:
        self.boundary = None
        self.answers = []

    def before_query(self, player: Any, *, forced: bool = False) -> AttemptAnswer:
        """Note that ``player`` is being asked; the first query of a try is the
        rejection boundary of a resolution or priority attempt."""
        if self.boundary is None:
            from engine.rollback import take_snapshot

            self.boundary = take_snapshot(self.game, *self.roots)
        record = AttemptAnswer(player, forced=forced)
        self.answers.append(record)
        return record

    def owner(self, error: InvalidPlayerChoiceError) -> AttemptAnswer | None:
        # A forced answer owns a rejection only when no answer made a decision.
        decisions = [a for a in self.answers if not a.forced] or self.answers
        if not decisions:
            return None
        # A combat declaration is legal or illegal as a whole (rules 508.1, 509.1).
        whole = self.kind == "declaration" or _rejects_whole_action(error)
        return decisions[0] if whole else decisions[-1]

    @property
    def action_answer(self) -> AttemptAnswer | None:
        """The answer that chose a priority action or a declaration, in the
        current try."""
        return self.answers[0] if self.kind in ("priority", "declaration") and self.answers else None

    def reject(self, error: InvalidPlayerChoiceError) -> None:
        """Tell the owning answer's player about a rejection, after the
        rollback; a rejection it raises, or one nobody owns, is final
        (:class:`_Final`)."""
        owner = self.owner(error)
        if owner is None:
            raise _Final(error)
        try:
            owner.player.on_attempt_rejected(self, owner, error)
        except InvalidPlayerChoiceError as refused:
            raise _Final(refused) from refused


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
    """A rejection its owner raised, or no one owns, on its way out of every
    attempt.

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


def resolve(game: Any, obj: Any) -> None:
    """Run the resolving object ``obj``'s effect as an attempt whose actor is
    its controller; a rejected choice runs it again from the state before its
    first query. ``obj`` — the popped StackObject — is rolled back with the
    game."""
    context = AttemptContext(
        game, "resolution", actor=getattr(obj, "controller", None), action=obj
    )
    _run(context, lambda: obj.on_resolve(game), (obj,))


def attempt(game: Any, operation: Callable[[], Any]) -> Any:
    """Run one cast or choice ``operation`` as its own attempt while an object
    resolves, and return its result. A rejection rolls back only the
    operation, keeping everything before it, and runs it again."""
    return _run(AttemptContext(game, "choice"), operation, ())


def _run(context: AttemptContext, operation: Callable[[], Any], roots: tuple[Any, ...]) -> Any:
    from engine.priority import REJECTED_ACTION_ERRORS, as_choice_error
    from engine.rollback import take_snapshot

    # The operation's own state (its closure) is part of what a retry restores.
    context.roots = (operation, *roots)
    start = take_snapshot(context.game, *context.roots)
    with active(context):
        while True:
            context.begin_try()
            if context.kind == "choice":
                context.boundary = start
            try:
                return operation()
            except REJECTED_ACTION_ERRORS as exc:
                (context.boundary or start).restore()
                context.reject(as_choice_error(exc))
                start.restore()


def _rejects_whole_action(error: InvalidPlayerChoiceError) -> bool:
    from engine.priority import REJECTED_ACTION_ERRORS

    cause = error.__cause__
    return isinstance(cause, REJECTED_ACTION_ERRORS) and not isinstance(
        cause, InvalidPlayerChoiceError
    )
