"""The Test Interface: how Audited Tests build a game, play it and look at it.

This module is fixed: do not change it. See ``test_interface.md``.

A test plays two novice players who have come to a board state. It builds the
position with :func:`create_game`, gives each player a script of
:class:`Entry` answers, and lets :func:`run` play: the engine asks the players
its questions, the scripts answer them, and the test sees the game only
through :func:`view`, the Player View.
"""

from __future__ import annotations

import enum
import signal
import threading
import time
import weakref
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Self

from engine.card import printed_class
from engine.decisions import Decision, InvalidPlayerChoiceError, PlayerDecision, satisfies
from engine.game import Side as _EngineSide
from engine.game import create_game as _engine_create_game
from engine.player import Player
from engine.queries import Answer, PlayerQuery, asks_for, is_action_query, is_declaration_query
from engine.turn import advance
from engine.types import ManaType, Phase, Step, Zone

__all__ = [
    "QUESTION_TIMEOUT",
    "Branch",
    "ChanceResult",
    "Decision",
    "Entry",
    "Handle",
    "Kind",
    "ManaType",
    "Phase",
    "PlayDiverged",
    "PlayerView",
    "ScriptedPlayer",
    "Seen",
    "Side",
    "SourcedAbility",
    "Step",
    "Token",
    "View",
    "Zone",
    "ability",
    "act",
    "act_illegal",
    "branch",
    "card",
    "chosen_at_random",
    "coin",
    "create_game",
    "pass_priority",
    "player",
    "run",
    "shuffled",
    "token",
    "view",
]

# Seconds the engine may take between one question and the next.
QUESTION_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class Handle:
    """A constructed card, followed as a physical card across zones.

    Made with :func:`card` and placed by :func:`create_game`. A token is
    followed by its :class:`Token` instead.
    """

    _count = 0

    def __init__(self, cls: type, tapped: bool) -> None:
        Handle._count += 1
        self.number = Handle._count
        self.cls = cls
        self.tapped = tapped
        self.card: Any = None

    def __repr__(self) -> str:
        return f"<{self.cls.__name__} #{self.number}>"


def card(cls: type, *, tapped: bool = False) -> Handle:
    """A card of predefined class ``cls`` to place, and the handle to follow
    it by; ``tapped`` starts a permanent tapped."""
    if not isinstance(cls, type):
        raise TypeError(f"a card is placed by its predefined class, not {cls!r}")
    return Handle(cls, tapped)


@dataclass
class Side:
    """One player's part of the starting position.

    Each zone lists cards as predefined classes or :func:`card` handles; the
    library is listed top first. ``mana`` is what the player's mana pool holds.
    """

    library: Sequence[type | Handle] = ()
    hand: Sequence[type | Handle] = ()
    battlefield: Sequence[type | Handle] = ()
    graveyard: Sequence[type | Handle] = ()
    exile: Sequence[type | Handle] = ()
    life: int = 20
    mana: Mapping[ManaType, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Token:
    """A token, followed by its number: the game's tokens are numbered in
    the order the game makes them, so ``token(1)`` is the first token made,
    and a token keeps its number after it leaves the battlefield.

    Tokens made together — those one effect creates — are numbered seat 0's
    before seat 1's, each seat's in the order the effect creates them;
    tokens an effect makes alike are interchangeable. A token a rejected
    attempt made gives its number back. A token has no class: what it is
    shows in what it does.
    """

    number: int

    def __repr__(self) -> str:
        return f"token {self.number}"


def token(number: int) -> Token:
    """The ``number``-th token the game makes, counting from 1."""
    if number < 1:
        raise ValueError(f"tokens are numbered from 1, not {number}")
    return Token(number)


class _Tokens:
    """A game's tokens in the order they were numbered.

    Numbers come from the engine's record of the tokens it made,
    ``game.created_tokens``, so a token that has left the battlefield keeps
    its number. A rollback undoes the tokens a rejected attempt made; their
    numbers are given back, and tokens made again on the retry take them.
    """

    def __init__(self) -> None:
        self.objects: list[Any] = []
        self.by_id: dict[int, Token] = {}

    def number(self, game: Any) -> None:
        """Number every token the game has made that has no number yet.

        Tokens made since the last numbering are numbered seat 0's first,
        each seat's in the order they were made.
        """
        made = game.created_tokens
        kept = {id(obj) for obj in made}
        valid = 0
        while valid < len(self.objects) and id(self.objects[valid]) in kept:
            valid += 1
        del self.objects[valid:]
        numbered = {id(obj) for obj in self.objects}
        fresh = [obj for obj in made if id(obj) not in numbered]
        fresh.sort(key=lambda obj: _seat_of(game, obj))
        self.objects.extend(fresh)
        self.by_id = {id(obj): Token(n) for n, obj in enumerate(self.objects, 1)}

    def find(self, game: Any, followed: Token) -> Any:
        """The token object ``followed`` names, or ``None`` if the game has
        made no token with that number."""
        self.number(game)
        if followed.number > len(self.objects):
            return None
        return self.objects[followed.number - 1]


def _seat_of(game: Any, obj: Any) -> int:
    owner = getattr(obj, "owner", None)
    for seat, scripted in enumerate(game.players):
        if scripted is owner:
            return seat
    return len(game.players)


# Each game's tokens.
_TOKENS: weakref.WeakKeyDictionary[Any, _Tokens] = weakref.WeakKeyDictionary()


def _tokens(game: Any) -> _Tokens:
    tokens = _TOKENS.get(game)
    if tokens is None:
        tokens = _TOKENS[game] = _Tokens()
    return tokens


# Each game's handles, by the identity of the card each follows.
_HANDLES: weakref.WeakKeyDictionary[Any, dict[int, Handle]] = weakref.WeakKeyDictionary()
# The player being asked the current action question, by game.
_ASKED: weakref.WeakKeyDictionary[Any, int] = weakref.WeakKeyDictionary()


def create_game(p0: Side | None = None, p1: Side | None = None, *, start: tuple[Step | Phase, int]) -> Any:
    """Build the starting position and return the game.

    ``start=(step, active)`` opens ``step`` — a :class:`Step`, or a main
    :class:`Phase` — of seat ``active``'s turn with its priority window open.
    Permanents are not summoning sick, carry no counters or damage, and a
    planeswalker has its printed loyalty; nothing is shuffled. Anything else
    the test needs is reached through play.
    """
    players = (ScriptedPlayer("Player 0"), ScriptedPlayer("Player 1"))
    handles: dict[int, Handle] = {}
    sides = []
    for seat, side in enumerate((p0 or Side(), p1 or Side())):
        built: dict[str, list[Any]] = {}
        tapped: list[Any] = []
        for zone in ("library", "hand", "battlefield", "graveyard", "exile"):
            built[zone] = []
            for item in getattr(side, zone):
                handle = item if isinstance(item, Handle) else card(item)
                if handle.card is not None:
                    raise ValueError(f"{handle!r} is already placed")
                handle.card = handle.cls()
                handles[id(handle.card)] = handle
                built[zone].append(handle.card)
                if handle.tapped:
                    if zone != "battlefield":
                        raise ValueError(f"only a permanent starts tapped, not {handle!r} in {zone}")
                    tapped.append(handle.card)
        sides.append(_EngineSide(**built, tapped=tapped, life=side.life, mana=dict(side.mana)))
    game = _engine_create_game(*players, start=start, sides=tuple(sides))
    for seat, scripted in enumerate(players):
        scripted.game, scripted.seat = game, seat
    _HANDLES[game] = handles
    return game


# ---------------------------------------------------------------------------
# The Player View
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Seen:
    """One object as a player sees it: what it is, whose it is, and whether
    it is tapped. ``handle`` follows a constructed card."""

    card: type | None
    owner: int
    tapped: bool = False
    handle: Handle | Token | None = None

    def _key(self) -> tuple:
        cls = self.card
        name = "" if cls is None else f"{cls.__module__}.{cls.__qualname__}"
        kind = 0 if self.handle is None else 1 if isinstance(self.handle, Handle) else 2
        return (name, self.tapped, kind, self.handle.number if self.handle else 0)

    def __repr__(self) -> str:
        tapped = " tapped" if self.tapped else ""
        if isinstance(self.handle, Token):
            return f"{self.handle!r}{tapped}"
        name = "?" if self.card is None else self.card.__name__
        handle = f" #{self.handle.number}" if self.handle else ""
        return f"{name}{handle}{tapped}"


# Zones whose order a player cannot see or rely on.
_UNORDERED = ("hand", "battlefield", "graveyard", "exile")


@dataclass(frozen=True)
class PlayerView:
    """One player's side of the table. ``library`` is top first; the other
    zones are compared without regard to order."""

    life: int
    library: tuple[Seen, ...] = ()
    hand: tuple[Seen, ...] = ()
    battlefield: tuple[Seen, ...] = ()
    graveyard: tuple[Seen, ...] = ()
    exile: tuple[Seen, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "library", tuple(self.library))
        for zone in _UNORDERED:
            object.__setattr__(self, zone, tuple(sorted(getattr(self, zone), key=Seen._key)))


@dataclass(frozen=True)
class View:
    """The Player View: everything a player at the table can see.

    ``stack`` is top first; ``step`` is a :class:`Step`, or a main
    :class:`Phase`; ``active`` and ``asked`` are seats, ``asked`` being the
    player whose action question the game is at; ``winner`` is a seat, or
    ``None`` while the game goes on or after a draw.
    """

    players: tuple[PlayerView, PlayerView]
    stack: tuple[Seen, ...]
    step: Step | Phase
    active: int
    asked: int | None
    game_over: bool = False
    winner: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "players", tuple(self.players))
        object.__setattr__(self, "stack", tuple(self.stack))

    def where(self, handle: Handle | Token) -> Zone | None:
        """The zone ``handle``'s card or token is in, or ``None`` if it is in
        none."""
        if any(seen.handle == handle for seen in self.stack):
            return Zone.STACK
        for side in self.players:
            for zone in ("library", *_UNORDERED):
                if any(seen.handle == handle for seen in getattr(side, zone)):
                    return Zone(zone)
        return None

    def describe(self) -> str:
        lines = [
            f"step {_step_name(self.step)}, player {self.active}'s turn, "
            f"player {self.asked} asked"
            + (f"; game over, winner {self.winner}" if self.game_over else "")
        ]
        for seat, side in enumerate(self.players):
            lines.append(f"player {seat}: life {side.life}")
            for zone in ("library", *_UNORDERED):
                cards = getattr(side, zone)
                if cards:
                    lines.append(f"  {zone}: {', '.join(map(repr, cards))}")
        if self.stack:
            lines.append(f"stack: {', '.join(map(repr, self.stack))}")
        return "\n".join(lines)


def view(game: Any) -> View:
    """A frozen snapshot of what the players can see of ``game``."""
    handles = _HANDLES.get(game, {})
    tokens = _tokens(game)
    tokens.number(game)

    def handle(obj: Any) -> Handle | Token | None:
        physical = id(game.refs.physical_card(obj))
        return handles.get(physical) or tokens.by_id.get(physical)

    def seen(obj: Any, owner: int, tapped: bool = False) -> Seen:
        printed = None if getattr(obj, "is_token", False) else _printed(obj)
        return Seen(printed, owner, tapped, handle(obj))

    sides = []
    for seat, scripted in enumerate(game.players):
        zones = scripted.zones
        sides.append(PlayerView(
            life=scripted.life,
            library=tuple(seen(c, seat) for c in reversed(zones[Zone.LIBRARY].get_all())),
            hand=tuple(seen(c, seat) for c in zones[Zone.HAND].get_all()),
            battlefield=tuple(
                seen(c, seat, bool(getattr(c, "is_tapped", False)))
                for c in zones[Zone.BATTLEFIELD].get_all()
            ),
            graveyard=tuple(seen(c, seat) for c in zones[Zone.GRAVEYARD].get_all()),
            exile=tuple(seen(c, seat) for c in zones[Zone.EXILE].get_all()),
        ))
    stack = tuple(
        Seen(
            _stack_printed(obj),
            _seat(game, obj.controller),
            False,
            # A spell is its card; an ability is not the card it comes from.
            handle(obj),
        )
        for obj in game.stack.objects()
    )
    over = bool(game.is_game_over)
    winner = None if game.winner is None else _seat(game, game.winner)
    asked = None if over else _ASKED.get(game, game.priority_player_index)
    return View(
        players=tuple(sides),
        stack=stack,
        step=game.step if game.step is not None else game.phase,
        active=game.active_player_index,
        asked=asked,
        game_over=over,
        winner=winner,
    )


def _printed(obj: Any) -> type | None:
    printed = getattr(obj, "printed", None)
    return printed if isinstance(printed, type) else printed_class(obj)


def _stack_printed(obj: Any) -> type | None:
    printed = getattr(obj, "printed", None)
    return printed if isinstance(printed, type) else _printed(obj.source)


def _seat(game: Any, who: Any) -> int:
    return next(seat for seat, candidate in enumerate(game.players) if candidate is who)


def _step_name(step: Step | Phase) -> str:
    return step.value.replace("_", " ")


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------


class Kind(enum.Enum):
    ACT = "act"
    ILLEGAL = "act_illegal"
    PASS = "pass_priority"


@dataclass(frozen=True)
class Branch:
    """One way to answer an entry's questions.

    ``preferences`` choose the action, in order — the first preference an
    offered option satisfies wins — and, with ``choices`` after them, answer
    every other question of the entry. ``per_query`` pairs a key with the
    preferences that answer, instead, a question the key matches: an object
    the question's payload holds, or a predicate over the query; keys are
    tried in order and the first match wins. With ``distinct``, the branch
    never chooses an object that an answer of this entry still in effect
    already chose for a question from the same source object.

    At a combat declaration ``preferences`` are the creatures declared, every
    one of them, and ``scoped`` pairs a creature with exactly what it attacks
    or blocks: never filled in or trimmed, judged on the declaration that
    would take effect, and the branch is withdrawn when it cannot be met.
    """

    preferences: tuple[Any, ...] = ()
    choices: tuple[Any, ...] = ()
    per_query: tuple[tuple[Any, tuple[Any, ...]], ...] = ()
    distinct: bool = False
    scoped: tuple[tuple[Any, tuple[Any, ...]], ...] = ()

    def matched(self, query: PlayerQuery) -> tuple[Any, ...] | None:
        """The first matching ``per_query`` key's preferences, or ``None``."""
        for key, preferences in self.per_query:
            if callable(key) and not isinstance(key, type):
                if key(query):
                    return preferences
            elif asks_for(query, key):
                return preferences
        return None


def branch(
    *preferences: Any,
    choices: Iterable[Any] = (),
    per_query: Mapping[Any, Any] | None = None,
    distinct: bool = False,
    scoped: Mapping[Any, Any] | None = None,
) -> Branch:
    """A branch, e.g. ``branch(A, B, per_query={CardType.ARTIFACT: [A],
    CardType.CREATURE: [B]})``, or at a declaration
    ``branch(wall, scoped={wall: bear})``."""
    return Branch(
        _items(preferences), _items(choices), _per_query(per_query), distinct, _scoped(scoped)
    )


@dataclass(frozen=True)
class Entry:
    """One answer in a player's script: it answers the player's next action
    question and every other question they receive until the one after.

    ``view`` is the Player View expected at the next action question, any
    player's; an entry without one changes nothing the view shows.
    ``narration`` says in plain English what the entry does.
    """

    kind: Kind
    branches: tuple[Branch, ...] = (Branch(),)
    view: View | None = None
    note: str = ""
    narration: str = ""

    def describe(self) -> str:
        text = self.narration or self._summary()
        return f"{text} ({self.note})" if self.note else text

    def _summary(self) -> str:
        return self.kind.value + " | ".join(
            "(" + ", ".join(map(_describe_item, b.preferences + b.choices)) + ")" for b in self.branches
        )


def act(
    *preferences: Any,
    choices: Iterable[Any] = (),
    per_query: Mapping[Any, Any] | None = None,
    distinct: bool = False,
    scoped: Mapping[Any, Any] | None = None,
    branches: Iterable[Any] | None = None,
    view: View | None = None,
    note: str = "",
) -> Entry:
    """An action the player must take.

    ``preferences``, ``choices``, ``per_query``, ``distinct`` and ``scoped``
    make one branch; ``branches`` lists several instead, each a list of
    preferences or a :func:`branch`, with ``choices``, ``per_query`` and
    ``scoped`` added to every one. A branch whose action is not offered is
    skipped, and each rejection of an answer the entry gave moves it to its
    next branch. A preference is a Player Decision, a predefined class, a
    :func:`card` handle or a :func:`player`.

    At a combat declaration the preferences are every creature declared, and
    ``scoped`` maps a creature to what it attacks or blocks, e.g.
    ``act(wall, scoped={wall: bear})`` blocks the bear with the wall.
    """
    return Entry(Kind.ACT, _branches(preferences, choices, per_query, distinct, branches, scoped), view, note)


def act_illegal(
    *preferences: Any,
    choices: Iterable[Any] = (),
    per_query: Mapping[Any, Any] | None = None,
    distinct: bool = False,
    scoped: Mapping[Any, Any] | None = None,
    branches: Iterable[Any] | None = None,
    view: View | None = None,
    note: str = "",
) -> Entry:
    """An action the rules forbid — a cast, an activation or a declaration:
    satisfied when every branch is not offered or rejected, after which the
    same question goes to the next entry; play diverges if any branch takes
    effect."""
    return Entry(Kind.ILLEGAL, _branches(preferences, choices, per_query, distinct, branches, scoped), view, note)


def pass_priority(
    *,
    choices: Iterable[Any] = (),
    per_query: Mapping[Any, Any] | None = None,
    distinct: bool = False,
    branches: Iterable[Any] | None = None,
    view: View | None = None,
    note: str = "",
) -> Entry:
    """Pass — or, at a combat declaration, declare nothing — with ``choices``
    for the questions that follow before the player's next action question — or ``branches`` of them, each a
    :func:`branch` or a list of choices, tried in turn after rejections."""
    if branches is None:
        return Entry(Kind.PASS, (Branch((), _items(choices), _per_query(per_query), distinct),), view, note)
    built = tuple(
        b if isinstance(b, Branch) else Branch((), _items(b), (), distinct) for b in branches
    )
    if any(b.preferences for b in built):
        raise TypeError("a pass takes no action, so its branches hold only choices")
    return Entry(
        Kind.PASS,
        _branches((), choices, per_query, distinct, built),
        view,
        note,
    )


@dataclass(frozen=True)
class SourcedAbility:
    """An ability of one permanent: the printed ability ``printed`` of the
    card or token ``source``, made with :func:`ability`."""

    source: Handle | Token
    printed: type

    def __repr__(self) -> str:
        return f"{self.printed.__name__} of {self.source!r}"


def ability(source: Handle | Token, printed: type) -> SourcedAbility:
    """The printed ability ``printed`` of ``source``'s permanent: an option
    is chosen only when it is that ability and ``source`` is where it comes
    from — so one of several objects with the same printed ability, such as
    a card's own and the one it grants another permanent, can be named."""
    if not isinstance(source, (Handle, Token)):
        raise TypeError(f"an ability's source is a card(...) handle or a token(n), not {source!r}")
    if not isinstance(printed, type):
        raise TypeError(f"an ability is named by its predefined class, not {printed!r}")
    return SourcedAbility(source, printed)


def player(seat: int) -> PlayerDecision:
    """The preference that chooses the player in ``seat``."""
    return Decision.player(seat=seat)


def _branches(
    preferences: Any, choices: Any, per_query: Any, distinct: bool, branches: Any, scoped: Any = None
) -> tuple[Branch, ...]:
    shared, shared_per_query, shared_scoped = _items(choices), _per_query(per_query), _scoped(scoped)
    if branches is None:
        return (Branch(_items(preferences), shared, shared_per_query, distinct, shared_scoped),)
    if preferences:
        raise TypeError("an entry takes preferences or branches, not both")
    built = tuple(
        replace(
            b,
            choices=b.choices + shared,
            per_query=b.per_query + shared_per_query,
            scoped=b.scoped + shared_scoped,
        )
        if isinstance(b, Branch)
        else Branch(_items(b), shared, shared_per_query, distinct, shared_scoped)
        for b in branches
    )
    if not built:
        raise TypeError("an entry needs at least one branch")
    return built


def _items(items: Iterable[Any]) -> tuple[Any, ...]:
    out = []
    for item in items:
        if not isinstance(item, (PlayerDecision, Handle, Token, SourcedAbility, type)):
            raise TypeError(
                "a preference is a Player Decision, a predefined class, a handle, a token or an ability of one,"
                f" not {item!r}"
            )
        out.append(item)
    return tuple(out)


def _per_query(mapping: Mapping[Any, Any] | None) -> tuple[tuple[Any, tuple[Any, ...]], ...]:
    pairs = []
    for key, preferences in (mapping or {}).items():
        if isinstance(key, str) and not isinstance(key, enum.Enum):
            raise TypeError(f"a per_query key is a payload object or a predicate, not a string: {key!r}")
        values = preferences if isinstance(preferences, (list, tuple)) else (preferences,)
        pairs.append((key, _items(values)))
    return tuple(pairs)


def _scoped(mapping: Mapping[Any, Any] | None) -> tuple[tuple[Any, tuple[Any, ...]], ...]:
    pairs = []
    for key, values in (mapping or {}).items():
        values = values if isinstance(values, (list, tuple)) else (values,)
        pairs.append((_items((key,))[0], _items(values)))
    return tuple(pairs)


def _describe_item(item: Any) -> str:
    if isinstance(item, (type, Handle, Token, SourcedAbility)):
        return item.__name__ if isinstance(item, type) else repr(item)
    attrs = dict(item.attrs)
    printed = attrs.get("printed")
    if isinstance(printed, type):
        return printed.__name__
    if "seat" in attrs:
        return f"player {attrs['seat']}"
    return repr(attrs)


# ---------------------------------------------------------------------------
# Chance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChanceResult:
    """The result the test gives one random event."""

    kind: str
    items: tuple[Any, ...] = ()
    heads: bool = False


def shuffled(*cards: type | Handle) -> ChanceResult:
    """A shuffle's result: the shuffled cards in their new order — a library
    top first — each a class or a handle."""
    return ChanceResult("shuffle", tuple(cards))


def chosen_at_random(*items: Any) -> ChanceResult:
    """What a choice at random picks: cards by class or handle, players by
    :func:`player`, or the very options offered."""
    return ChanceResult("choose_at_random", tuple(items))


def coin(heads: bool) -> ChanceResult:
    """A coin flip's result."""
    return ChanceResult("flip_coin", heads=heads)


class _Chance:
    """Answers a game's randomness hooks from the test's chance script; its
    position rolls back with the game, since it is reached from it."""

    rollback_exempt = frozenset({"_run"})

    def __init__(self, run: _Run, results: Sequence[ChanceResult]) -> None:
        self._run = run
        self._results = list(results)

    def shuffle(self, cards: list[Any]) -> list[Any]:
        result = self._next("shuffle")
        return self._arrange(result.items, list(cards), exact=True)

    def choose_at_random(self, options: list[Any], n: int) -> list[Any]:
        result = self._next("choose_at_random")
        chosen = self._arrange(result.items, list(options), exact=False)
        if len(chosen) != n:
            self._run.diverge(f"a choice at random of {n} was given {len(chosen)}")
        return chosen

    def flip_coin(self) -> bool:
        return self._next("flip_coin").heads

    def _next(self, kind: str) -> ChanceResult:
        if not self._results:
            self._run.diverge(f"a random event ({kind}) has nothing in the chance script to answer it")
        result = self._results.pop(0)
        if result.kind != kind:
            self._run.diverge(f"the chance script gives a {result.kind} result to a {kind}")
        return result

    def _arrange(self, items: Sequence[Any], pool: list[Any], *, exact: bool) -> list[Any]:
        handles = _HANDLES.get(self._run.game, {})
        arranged = []
        for item in items:
            for candidate in pool:
                if _is(item, candidate, handles, self._run.game):
                    arranged.append(candidate)
                    pool.remove(candidate)
                    break
            else:
                self._run.diverge(f"the chance script names {_describe_item(item)}, which is not among {pool!r}")
        if exact and pool:
            self._run.diverge(f"the chance script leaves {pool!r} out of a shuffle")
        return arranged


def _is(item: Any, candidate: Any, handles: dict[int, Handle], game: Any) -> bool:
    if isinstance(item, Handle):
        return handles.get(id(candidate)) is item
    if isinstance(item, Token):
        return _tokens(game).find(game, item) is candidate
    if isinstance(item, type):
        return _printed(candidate) is item
    if isinstance(item, PlayerDecision):
        if item.kind.value != "player" or not any(candidate is p for p in game.players):
            return False
        seat = dict(item.attrs).get("seat")
        return seat is None or game.players[seat] is candidate
    return item is candidate or item == candidate


# ---------------------------------------------------------------------------
# The scripted player
# ---------------------------------------------------------------------------


class _Diverged(BaseException):
    """Play left the scripts. A BaseException, so engine code that turns its
    own failures into rejections never mistakes it for one."""


class _Stopped(BaseException):
    """Every script has run out."""


class _Withdrawn(InvalidPlayerChoiceError):
    """A player withdraws a declaration branch whose scoped answers cannot be
    met. The engine refused nothing, but withdrawing it as a rejection rolls
    the declaration back before anything takes effect, and the re-asked
    declaration goes to the entry's next branch."""


class PlayDiverged(AssertionError):
    """Play left the test's scripts or views; the message narrates the script
    up to where it diverged, the question then asked, and the expected view
    against the actual one."""


@dataclass(eq=False)
class _Playing:
    """The entry a player is playing, the branch it answers with, and
    whether its action question is being asked again after a rejection.

    ``generation`` names the entry for as long as the player lives: each entry
    a player starts, in this run or a later one, takes the next number, and a
    retry of the same entry keeps it."""

    entry: Entry
    generation: int
    branch: int = 0
    reasked: bool = False
    rejected: InvalidPlayerChoiceError | None = None
    # A declaration's preferences are a set of creatures, not alternatives.
    declaration: bool = False

    @property
    def current(self) -> Branch:
        return self.entry.branches[min(self.branch, len(self.entry.branches) - 1)]


class ScriptedPlayer(Player):
    """A player who answers every question from their script, and nothing
    else: no defaults, no guesses."""

    # Script position and entry numbering are the test's, not the game's, so a
    # rollback leaves them; the objects an entry chose are the game's, and a
    # rollback undoes them.
    rollback_exempt = frozenset({"game", "seat", "script", "_playing", "_run", "_entries"})

    def __init__(self, name: str, life: int = 20) -> None:
        super().__init__(name, life)
        self.game: Any = None
        self.seat: int | None = None
        self.script: list[Entry] = []
        self._playing: _Playing | None = None
        self._run: _Run | None = None
        self._entries = 0
        # (entry generation, question source, chosen object) for ``distinct``.
        self._chosen: list[tuple[int, Any, Any]] = []

    def answer(self, query: PlayerQuery) -> Answer:
        run = self._run
        if run is None:
            raise RuntimeError("a ScriptedPlayer answers only while run() plays")
        run.asked(query)
        if is_action_query(query):
            return self._action_question(run, query)
        return self._question(run, query)

    def on_attempt_rejected(self, context: Any, answer: Any, error: InvalidPlayerChoiceError) -> None:
        playing, run = self._playing, self._run
        if playing is None or run is None:
            raise error
        action = getattr(context, "kind", None) in ("priority", "declaration")
        actor = getattr(context, "actor", None)
        if action and isinstance(actor, ScriptedPlayer) and actor._playing is not None:
            # The actor's action question is asked again, whoever owns the rejection.
            actor._playing.reasked = True
        whole_action = action and actor is self
        playing.rejected = error
        playing.branch += 1
        if playing.branch < len(playing.entry.branches):
            return
        if playing.entry.kind is Kind.ILLEGAL and whole_action:
            return
        run.diverge(f"player {self.seat}'s {playing.entry.describe()} was rejected with no branch left: {error}")

    def on_action_ended(self, context: Any) -> None:
        playing, run = self._playing, self._run
        if playing is None or run is None or getattr(context, "actor", None) is not self:
            return
        if getattr(context, "taken", False) and playing.entry.kind is Kind.ILLEGAL:
            run.diverge(f"player {self.seat}'s {playing.entry.describe()} took effect")

    # -- answering ---------------------------------------------------------

    def _action_question(self, run: _Run, query: PlayerQuery) -> Answer:
        playing = self._playing
        if playing is not None and playing.reasked:
            playing.reasked = False
            run.compare(self.seat, again=True)
            chosen = self._choose_action(run, playing, query)
            if chosen is not None:
                return chosen
            run.completed(playing)
        else:
            run.action_question(self.seat)
        while True:
            if not self.script:
                run.out_of_script(self.seat)
            playing = self._start(self.script.pop(0), declaration=is_declaration_query(query))
            run.started(self.seat, playing)
            if playing.entry.kind is Kind.PASS:
                return Answer()
            chosen = self._choose_action(run, playing, query)
            if chosen is not None:
                return chosen
            run.completed(playing)

    def _start(self, entry: Entry, *, declaration: bool = False) -> _Playing:
        """Play ``entry`` next, under a generation no earlier entry had. Only
        the entry being played answers, so the choices earlier entries made
        are forgotten."""
        self._entries += 1
        self._playing = _Playing(entry, self._entries, declaration=declaration)
        self._chosen = []
        return self._playing

    def _choose_action(self, run: _Run, playing: _Playing, query: PlayerQuery) -> Answer | None:
        """The current branch's action — at a declaration, every creature it
        names — skipping branches whose action is not offered; ``None`` once
        an ``act_illegal`` entry has no branch left."""
        branches = playing.entry.branches
        while playing.branch < len(branches):
            current = branches[playing.branch]
            matched = self._matched(current, query)
            preferences = matched if matched is not None else current.preferences
            if playing.declaration:
                declared = self._exactly(query.options, preferences)
                if declared is not None:
                    return Answer(declared)
            else:
                for preference in self._matchers(preferences):
                    for option in query.options:
                        if self._matches(option, preference):
                            return Answer((option,))
            playing.branch += 1
        if playing.entry.kind is Kind.ACT:
            reason = "was rejected with no branch left" if playing.rejected else "is not offered"
            detail = f": {playing.rejected}" if playing.rejected else ""
            run.diverge(f"player {self.seat}'s {playing.entry.describe()} {reason}{detail}", query)
        return None

    def _question(self, run: _Run, query: PlayerQuery) -> Answer:
        playing = self._playing
        if playing is None:
            return self._select(run, query, (), None)
        current = playing.current
        for key, values in current.scoped:
            if any(self._satisfied(source, key) for source in query.source):
                answer = self._exactly(query.options, values)
                if answer is None or not query.min <= len(answer) <= query.max:
                    self._withdraw(run, playing, f"its scoped answer to {query.prompt!r} is not offered", query)
                return Answer(answer)
        matched = self._matched(current, query)
        preferences = current.preferences + current.choices if matched is None else matched
        return self._select(run, query, preferences, playing)

    def _matched(self, current: Branch, query: PlayerQuery) -> tuple[Any, ...] | None:
        """The first matching ``per_query`` key's preferences, or ``None``; a
        handle or class key matches a question whose payload names its card,
        as an option would."""
        for key, preferences in current.per_query:
            if callable(key) and not isinstance(key, type):
                hit = key(query)
            else:
                hit = asks_for(query, key) or (
                    isinstance(key, (Handle, Token, type))
                    and any(isinstance(i, PlayerDecision) and self._satisfied(i, key) for i in query.question)
                )
            if hit:
                return preferences
        return None

    def confirm_declaration(self, query: PlayerQuery, answer: Answer, outcome: tuple[Any, ...] = ()) -> None:
        """Withdraw a declaration that would give a declared creature something
        other than its scoped answer, whichever questions the engine asked."""
        playing, run = self._playing, self._run
        if playing is None or run is None or not playing.declaration:
            return
        for key, values in playing.current.scoped:
            for creature, targets in outcome:
                if self._satisfied(creature, key) and self._exactly(targets, values, every=True) is None:
                    self._withdraw(run, playing, "a declared creature's declaration differs from its scoped answer", query)

    def _withdraw(self, run: _Run, playing: _Playing, detail: str, query: PlayerQuery) -> None:
        """The branch's declaration is not offered as scoped: an ``act`` on its
        last branch diverges; otherwise the branch is withdrawn before anything
        takes effect, and the entry answers the re-asked declaration with its
        next branch."""
        if playing.entry.kind is Kind.ACT and playing.branch + 1 >= len(playing.entry.branches):
            run.diverge(f"player {self.seat}'s {playing.entry.describe()} is not offered: {detail}", query)
        raise _Withdrawn(f"{playing.entry.describe()}: {detail}")

    def _exactly(
        self, options: Sequence[PlayerDecision], wanted: Sequence[Any], *, every: bool = False
    ) -> tuple[PlayerDecision, ...] | None:
        """One option for each of ``wanted``, each a different one, or ``None``
        when one is missing; with ``every``, also ``None`` when an option is
        left over."""
        remaining = list(options)
        chosen = []
        for item in wanted:
            option = next((o for o in remaining if self._satisfied(o, item)), None)
            if option is None:
                return None
            chosen.append(option)
            remaining.remove(option)
        return None if every and remaining else tuple(chosen)

    def _satisfied(self, option: PlayerDecision, item: Any) -> bool:
        return any(self._matches(option, matcher) for matcher in self._matchers((item,)))

    def _select(
        self,
        run: _Run,
        query: PlayerQuery,
        preferences: Sequence[Any],
        playing: _Playing | None,
    ) -> Answer:
        """Preference-major selection: each preference picks the first offered
        option it is satisfied by and that is not picked yet. A mandatory
        question with exactly one possible answer — one option, required — is
        filled, unless ``distinct`` rules that option out, whether the
        preferences came from the branch or an empty ``per_query`` answer.
        Any other shortfall diverges."""
        source = _source_key(query)
        options = list(query.options)
        # Only a question with exactly one possible answer is filled for the
        # script: an all-of-several question still leaves the order open, and
        # an ordering question is answered by its order.
        forced = len(options) == query.min <= 1
        if playing is not None and playing.current.distinct:
            taken = {obj for entry, src, obj in self._chosen if entry == playing.generation and src == source}
            options = [o for o in options if _object_key(o) not in taken]
        selected: list[PlayerDecision] = []
        for preference in self._matchers(preferences):
            if len(selected) >= query.max:
                break
            for option in options:
                if option not in selected and self._matches(option, preference):
                    selected.append(option)
                    break
        if len(selected) < query.min:
            if forced:
                selected += [o for o in options if o not in selected]
            if len(selected) < query.min:
                run.diverge(f"nothing in player {self.seat}'s script answers this question", query)
        if playing is not None:
            self._chosen.extend((playing.generation, source, _object_key(o)) for o in selected)
        return Answer(tuple(selected))

    def _matchers(self, items: Iterable[Any]) -> list[PlayerDecision | Handle | Token | SourcedAbility]:
        """Each preference as Player Decisions to satisfy — a class stands for
        the card, ability or mode it prints — or as a handle."""
        matchers: list[PlayerDecision | Handle | Token | SourcedAbility] = []
        for item in items:
            if isinstance(item, (PlayerDecision, Handle, Token, SourcedAbility)):
                matchers.append(item)
            else:
                matchers += [Decision.obj(printed=item), Decision.ability(printed=item), Decision.mode(printed=item)]
        return matchers

    def _matches(self, option: PlayerDecision, preference: PlayerDecision | Handle | Token | SourcedAbility) -> bool:
        """A handle matches an option that stands for its physical card, and
        a token one that stands for that token — for an ability, the
        permanent it belongs to; a sourced ability, that printed ability of
        that permanent."""
        if isinstance(preference, SourcedAbility):
            return satisfies(option, Decision.ability(printed=preference.printed)) and self._matches(option, preference.source)
        if isinstance(preference, Handle):
            return preference.card is not None and self.game.refs.physical_card(option) is preference.card
        if isinstance(preference, Token):
            followed = _tokens(self.game).find(self.game, preference)
            return followed is not None and self.game.refs.physical_card(option) is followed
        return satisfies(option, preference)


def _source_key(query: PlayerQuery) -> Any:
    keys = []
    for source in query.source:
        attrs = dict(source.attrs)
        keys.append((source.kind, attrs.get("instance", attrs.get("seat"))))
    return tuple(keys)


def _object_key(option: PlayerDecision) -> Any:
    attrs = dict(option.attrs)
    return attrs.get("instance", option)


# ---------------------------------------------------------------------------
# Playing
# ---------------------------------------------------------------------------


class _Run:
    """One run's progress: the expected view, the entries started so far,
    and the question being answered — the test's, so never rolled back."""

    rollback_exempt = frozenset({"game", "expected", "checking", "last", "narrated", "query", "deadline"})

    def __init__(self, game: Any, expect: View, checking: bool) -> None:
        self.game = game
        self.expected = expect
        self.checking = checking
        self.last: _Playing | None = None
        self.narrated: list[str] = []
        self.query: PlayerQuery | None = None
        self.deadline = time.monotonic() + QUESTION_TIMEOUT

    def asked(self, query: PlayerQuery) -> None:
        if time.monotonic() > self.deadline:
            self.diverge(f"the engine took more than {QUESTION_TIMEOUT:g} s between two questions")
        self.deadline = time.monotonic() + QUESTION_TIMEOUT
        self.query = query

    def action_question(self, seat: int) -> None:
        if self.last is not None:
            self.completed(self.last)
        self.compare(seat)

    def started(self, seat: int, playing: _Playing) -> None:
        self.last = playing
        self.narrated.append(f"player {seat}: {playing.entry.describe()}")

    def completed(self, playing: _Playing) -> None:
        if playing is self.last:
            self.last = None
            if playing.entry.view is not None:
                self.expected = playing.entry.view

    def compare(self, seat: int, *, again: bool = False) -> None:
        _ASKED[self.game] = seat
        if not self.checking:
            return
        actual = view(self.game)
        if actual != self.expected:
            self.diverge("the view differs from the expected view" + (" when asked again" if again else ""), actual=actual)

    def out_of_script(self, seat: int) -> None:
        waiting = [s for s, p in enumerate(self.game.players) if p.script]
        if waiting:
            self.diverge(f"player {seat}'s script ran out while player {waiting[0]}'s still has entries")
        raise _Stopped

    def finish(self) -> View:
        if self.last is not None:
            self.completed(self.last)
        leftover = [s for s, p in enumerate(self.game.players) if p.script]
        if self.game.is_game_over and leftover:
            self.diverge(f"the game ended with entries left in player {leftover[0]}'s script")
        final = view(self.game)
        if self.checking and final != self.expected:
            self.diverge("the final view differs from the expected view", actual=final)
        return final

    def diverge(self, reason: str, query: PlayerQuery | None = None, *, actual: View | None = None) -> None:
        query = query or self.query
        lines = [reason, "", "Script so far:"]
        lines += [f"  {i + 1}. {text}" for i, text in enumerate(self.narrated)] or ["  (nothing)"]
        if query is not None:
            lines += ["", f"Question: {query.prompt}", f"  options: {', '.join(map(_describe_item, query.options)) or '(none)'}",
                      f"  choose {query.min} to {query.max}"]
        if actual is not None:
            lines += ["", "Expected view:", self.expected.describe(), "", "Actual view:", actual.describe()]
        raise _Diverged("\n".join(lines))


def run(
    game: Any,
    *scripts: Sequence[Entry],
    chance: Sequence[ChanceResult] = (),
    expect: View | None = None,
    check_views: bool = True,
) -> View:
    """Play ``game`` from its scripts, one per seat, and return the final view.

    ``expect`` is the view expected at the first action question, by default
    the view as play begins. At every action question the view must equal the
    expected one, which each entry's ``view`` then replaces — an entry without
    a ``view`` expects nothing visible to change; questions inside an action
    or a resolution are answered without a check. ``check_views=False`` turns
    every view check off, for checking the interface's own play mechanics;
    an Audited Test never turns it off. Play stops when a
    player whose script is empty is asked and every script is empty, or when
    the game ends; either way the final view must be the expected one.
    ``chance`` answers every random event, in order.

    Raises:
        PlayDiverged: When play leaves the scripts or the expected views, or
            more than five seconds pass between two questions.
    """
    if len(scripts) != len(game.players):
        raise TypeError(f"run takes one script per player ({len(game.players)}), not {len(scripts)}")
    state = _Run(game, expect if expect is not None else view(game), check_views)
    players = list(game.players)
    for scripted, entries in zip(players, scripts):
        if not isinstance(scripted, ScriptedPlayer):
            raise TypeError("run plays a game made by test_interface.create_game")
        scripted.script = list(entries)
        scripted._playing = None
        scripted._run = state
    chance_source = _Chance(state, chance)
    game.shuffle = chance_source.shuffle
    game.choose_at_random = chance_source.choose_at_random
    game.flip_coin = chance_source.flip_coin
    try:
        with _Watchdog(state):
            while not game.is_game_over:
                advance(game)
            return state.finish()
    except _Stopped:
        return state.finish()
    except _Diverged as diverged:
        raise PlayDiverged(str(diverged)) from None
    finally:
        for scripted in players:
            scripted._run = None


class _Watchdog:
    """Fails the run when the engine goes more than :data:`QUESTION_TIMEOUT`
    seconds without a question, even inside an endless loop, by an alarm
    signal where one can be set (the main thread); elsewhere the gap is only
    measured when the next question arrives."""

    def __init__(self, state: _Run) -> None:
        self.state = state
        self.armed = threading.current_thread() is threading.main_thread() and hasattr(signal, "setitimer")

    def __enter__(self) -> Self:
        if self.armed:
            self.started = time.monotonic()
            self.previous_handler = signal.signal(signal.SIGALRM, self._alarm)
            self.previous_timer = signal.setitimer(signal.ITIMER_REAL, 0.25, 0.25)
        return self

    def _alarm(self, signum: int, frame: Any) -> None:
        outer = self.previous_timer[0]
        if outer and time.monotonic() - self.started >= outer and callable(self.previous_handler):
            self.previous_handler(signum, frame)
        if time.monotonic() > self.state.deadline:
            self.state.deadline = float("inf")
            self.state.diverge(f"the engine took more than {QUESTION_TIMEOUT:g} s between two questions")

    def __exit__(self, *exc: object) -> None:
        if self.armed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, self.previous_handler)
            remaining, interval = self.previous_timer
            if remaining:
                elapsed = time.monotonic() - self.started
                signal.setitimer(signal.ITIMER_REAL, max(remaining - elapsed, 0.001), interval)
