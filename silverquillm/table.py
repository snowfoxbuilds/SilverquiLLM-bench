"""Host-side helpers that write Audited Tests on the Test Interface.

A :class:`Table` follows the scripts a test writes, in the order the players
are asked, and fills in what the Test Interface needs from them: each entry's
expected view and its plain-English narration. The test states only what its
answers change on the board — a card moves, a token appears, a permanent taps,
a life total changes, the game ends — and the table works out the rest from
the rules: who is asked next (CR 117), the steps and turns that follow when
everyone passes, who declares attackers and blockers and whether the declare
blockers and combat damage steps happen (CR 508.8), the untap step and each
turn's draw from the known library.

These helpers need no engine. They live with the Audited Tests on the host and
never enter the Workspace; they import the benchmark's ``test_interface``,
which grading puts on the path.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any

_ZONES = ("library", "hand", "battlefield", "graveyard", "exile")


def _ti() -> Any:
    import test_interface

    return test_interface


# ---------------------------------------------------------------------------
# Changes: what a player can see change on the board
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Change:
    """One visible change an entry's answers cause."""

    kind: str
    item: Any = None
    zone: Any = None
    seat: int | None = None
    from_zone: Any = None
    value: Any = None

    def describe(self) -> str:
        name = _name(self.item)
        if self.kind == "moves":
            where = f"player {self.seat}'s " if self.seat is not None and self.zone.value != "stack" else ""
            place = "the stack" if self.zone.value == "stack" else f"{where}{self.zone.value}"
            position = " (bottom)" if self.value == "bottom" else ""
            return f"{name} moves to {place}{position}"
        if self.kind == "appears":
            return f"{name} appears on player {self.seat}'s battlefield"
        if self.kind == "ceases":
            return f"{name} leaves the game"
        if self.kind in ("taps", "untaps"):
            return f"{name} {'becomes tapped' if self.kind == 'taps' else 'untaps'}"
        if self.kind == "life":
            return f"player {self.seat}'s life becomes {self.value}"
        if self.kind == "on_stack":
            return f"{name} goes on the stack for player {self.seat}"
        if self.kind == "off_stack":
            return f"{name} leaves the stack"
        if self.kind == "ends":
            return "the game ends in a draw" if self.seat is None else f"player {self.seat} wins the game"
        return self.kind


def moves(item: Any, to: Any, *, seat: int | None = None, from_zone: Any = None, bottom: bool = False) -> Change:
    """``item`` — a handle, or a class when only one such card could move —
    moves to zone ``to``; ``seat`` is the side it lands on (by default its
    current one), ``from_zone`` narrows where a class is looked for, and
    ``bottom`` puts it at the bottom of a library."""
    return Change("moves", item, to, seat, from_zone, "bottom" if bottom else "top")


def appears(seat: int) -> Change:
    """A token appears on ``seat``'s battlefield. It takes the next token
    number: list the tokens one effect makes in the order it makes them;
    the table numbers seat 0's before seat 1's, as the Test Interface does."""
    return Change("appears", seat=seat)


def ceases(item: Any, seat: int | None = None) -> Change:
    """``item`` — a ``test_interface.Token``, or a handle — leaves the game."""
    return Change("ceases", item, seat=seat)


def taps(item: Any, seat: int | None = None) -> Change:
    """The permanent ``item`` becomes tapped."""
    return Change("taps", item, seat=seat)


def untaps(item: Any, seat: int | None = None) -> Change:
    """The permanent ``item`` becomes untapped."""
    return Change("untaps", item, seat=seat)


def life(seat: int, total: int) -> Change:
    """Player ``seat``'s life total becomes ``total``."""
    return Change("life", seat=seat, value=total)


def on_stack(cls: type, seat: int) -> Change:
    """An ability of predefined class ``cls`` goes on the stack, controlled by
    ``seat``; it is put on top."""
    return Change("on_stack", cls, seat=seat)


def off_stack(cls: type) -> Change:
    """The topmost stack object of class ``cls`` leaves the stack."""
    return Change("off_stack", cls)


def wins(seat: int) -> Change:
    """The game ends and player ``seat`` wins."""
    return Change("ends", seat=seat)


def draw_game() -> Change:
    """The game ends in a draw."""
    return Change("ends")


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


class ScriptError(Exception):
    """The test's scripts cannot be followed: a player acts out of turn, or a
    change names something that is not on the board."""


_TURN = (
    "UNTAP", "UPKEEP", "DRAW", "PRECOMBAT_MAIN", "BEGIN_COMBAT", "DECLARE_ATTACKERS",
    "DECLARE_BLOCKERS", "COMBAT_DAMAGE", "END_COMBAT", "POSTCOMBAT_MAIN", "END", "CLEANUP",
)
_NO_PRIORITY = ("UNTAP", "CLEANUP")


class Table:
    """Follows a game built by ``test_interface.create_game`` as its players
    are asked, and keeps each player's script with its expected views.

    Each call writes the entry of the player being asked: :meth:`act`,
    :meth:`act_illegal` and :meth:`pass_` take ``then``, the changes the
    entry's answers cause before the next action question, and ``note``, what
    the entry checks. :meth:`run` plays the scripts.

    Entering the declare attackers step — and the declare blockers step when
    something attacks — the next entry answers that step's declaration: an
    :meth:`act` names the creatures declared (``scoped`` says what each
    attacks or blocks), and :meth:`pass_` declares none. The step's priority
    window follows.
    """

    def __init__(self, game: Any) -> None:
        ti = _ti()
        self.game = game
        start = ti.view(game)
        self.start = start
        self._sides = [
            {zone: list(getattr(side, zone)) for zone in _ZONES} | {"life": side.life}
            for side in start.players
        ]
        self._stack: list[Any] = list(start.stack)
        self._step = start.step.name
        self._active = start.active
        self._asked = start.asked
        self._turn = 1 if start.active == 0 else 2
        self._passes = 0
        self._tokens = 0
        # The declaration being asked ("attackers" or "blockers"), and whether
        # anything attacks this combat.
        self._declaring: str | None = None
        self._attacking = False
        self._over = False
        self._winner: int | None = None
        self.scripts: list[list[Any]] = [[] for _ in start.players]
        self._derived: list[str] = []

    # -- writing the scripts --------------------------------------------------

    @property
    def asked(self) -> int | None:
        """The seat the next action question goes to."""
        return None if self._over else self._asked

    @property
    def expected(self) -> Any:
        """The view expected at the next action question."""
        return self._view()

    def act(self, seat: int, *preferences: Any, then: Iterable[Change] = (), note: str = "", **options: Any) -> Any:
        """``seat`` takes an action; ``options`` are those of
        ``test_interface.act`` (``choices``, ``per_query``, ``distinct``,
        ``branches``)."""
        entry = _ti().act(*preferences, **options)
        if self._declaring:
            return self._write(seat, entry, then, note, f"declares {self._declaring}: " + _wants(entry))
        return self._write(seat, entry, then, note, "acts: " + _wants(entry))

    def act_illegal(self, seat: int, *preferences: Any, then: Iterable[Change] = (), note: str = "", **options: Any) -> Any:
        """``seat`` tries an action the rules forbid; the same question then
        goes to their next entry."""
        entry = _ti().act_illegal(*preferences, **options)
        return self._write(seat, entry, then, note, f"tries {_wants(entry)}, which the rules forbid")

    def pass_(self, seat: int, *, then: Iterable[Change] = (), note: str = "", **options: Any) -> Any:
        """``seat`` passes; ``options`` are those of ``test_interface.pass_priority``."""
        entry = _ti().pass_priority(**options)
        choices = entry.branches[0].choices
        text = f"declares no {self._declaring}" if self._declaring else "passes"
        text += f", answering {', '.join(map(_name, choices))}" if choices else ""
        return self._write(seat, entry, then, note, text)

    def pass_to(self, step: Any, active: int | None = None) -> None:
        """Every player passes, on an empty stack, and declares nothing, until
        the game next reaches ``step`` — a ``Step``, or a main ``Phase`` — of
        ``active``'s turn (of any turn when ``active`` is ``None``): at its
        declaration, for a declaration step."""
        if self._stack:
            raise ScriptError("pass_to needs an empty stack")
        for _ in range(4 * len(_TURN) * len(self._sides)):
            self.pass_(self._asked)
            if self._over:
                raise ScriptError(f"the game ends before it reaches {step.name}")
            if self._passes == 0 and self._step == step.name and active in (None, self._active):
                return
        raise ScriptError(f"the game does not reach {step.name} within two turns")

    def run(self, chance: Sequence[Any] = ()) -> Any:
        """Play the scripts and return the final view."""
        return _ti().run(self.game, *self.scripts, chance=chance, expect=self.start)

    # -- following the rules --------------------------------------------------

    def _write(self, seat: int, entry: Any, then: Iterable[Change], note: str, text: str) -> Any:
        ti = _ti()
        if self._over:
            raise ScriptError("the game is over; nobody is asked anything")
        if seat != self._asked:
            raise ScriptError(f"player {seat} writes an entry, but player {self._asked} is asked next")
        changes = list(then)
        stack_before = len(self._stack)
        # Tokens that appear together are numbered seat 0's first (TEST-INTERFACE.md).
        appearing = sorted((i for i, c in enumerate(changes) if c.kind == "appears"), key=lambda i: changes[i].seat)
        for n, i in enumerate(appearing, self._tokens + 1):
            changes[i] = replace(changes[i], item=ti.Token(n))
        for change in changes:
            self._apply(change)
        self._derived = []
        if not self._over and self._declaring:
            if entry.kind is not ti.Kind.ILLEGAL:
                # The declaration is made — or declines — and the step's
                # priority window opens with the active player (CR 508.2, 509.2).
                if self._declaring == "attackers":
                    self._attacking = entry.kind is ti.Kind.ACT and any(b.preferences for b in entry.branches)
                self._declaring = None
                self._asked = self._active
                self._passes = 0
        elif not self._over:
            if entry.kind is ti.Kind.ACT:
                self._passes = 0
            elif entry.kind is ti.Kind.PASS:
                self._passes += 1
                self._asked = 1 - seat
                if self._passes == len(self._sides):
                    self._passes = 0
                    self._asked = self._active
                    if not stack_before:
                        self._end_step()
        narration = f"Player {seat} {text}"
        said = [c.describe() for c in changes] + self._derived
        if said:
            narration += "; " + "; ".join(said)
        entry = replace(entry, view=self._view(), note=note, narration=narration)
        self.scripts[seat].append(entry)
        return entry

    def _end_step(self) -> None:
        """The step ends: the game moves through the steps that follow, doing
        their turn-based actions, to the next one in which players receive
        priority (CR 500.2, 508.8)."""
        while True:
            index = _TURN.index(self._step) + 1
            if index == len(_TURN):
                self._turn += 1
                self._active = 1 - self._active
                index = 0
                self._derived.append(f"player {self._active}'s turn {self._turn} begins")
            self._step = _TURN[index]
            if self._step == "DECLARE_BLOCKERS" and not self._attacking:
                # Nothing was declared as an attacker (CR 508.8).
                self._step = "END_COMBAT"
            if self._step == "END_COMBAT":
                self._attacking = False
            if self._step in ("DECLARE_ATTACKERS", "DECLARE_BLOCKERS"):
                # The declaration is the step's turn-based action, asked of the
                # active player for attackers and the other for blockers.
                self._declaring = "attackers" if self._step == "DECLARE_ATTACKERS" else "blockers"
                self._asked = self._active if self._declaring == "attackers" else 1 - self._active
                self._derived.append(f"the game moves to {self._step.lower().replace('_', ' ')}")
                return
            if self._step == "UNTAP":
                for i, seen in enumerate(self._sides[self._active]["battlefield"]):
                    if seen.tapped:
                        self._sides[self._active]["battlefield"][i] = replace(seen, tapped=False)
            if self._step == "DRAW" and not (self._turn == 1 and self._active == 0):
                self._draw(self._active)
                if self._over:
                    return
            if self._step not in _NO_PRIORITY:
                self._asked = self._active
                self._derived.append(f"the game moves to {self._step.lower().replace('_', ' ')}")
                return

    def _draw(self, seat: int) -> None:
        library = self._sides[seat]["library"]
        if not library:
            self._over, self._winner = True, 1 - seat
            self._derived.append(f"player {seat} draws from an empty library and loses")
            return
        card = library.pop(0)
        self._sides[seat]["hand"].append(card)
        self._derived.append(f"player {seat} draws {card!r}")

    def _apply(self, change: Change) -> None:
        ti = _ti()
        if change.kind == "life":
            self._sides[change.seat]["life"] = change.value
        elif change.kind == "ends":
            self._over, self._winner = True, change.seat
        elif change.kind == "appears":
            self._tokens = max(self._tokens, change.item.number)
            self._sides[change.seat]["battlefield"].append(ti.Seen(None, change.seat, False, change.item))
        elif change.kind == "on_stack":
            self._stack.insert(0, ti.Seen(change.item, change.seat))
        elif change.kind == "off_stack":
            index = next((i for i, s in enumerate(self._stack) if s.card is change.item), None)
            if index is None:
                raise ScriptError(f"no {_name(change.item)} on the stack")
            del self._stack[index]
        elif change.kind in ("taps", "untaps"):
            zone, index, seen = self._find(change.item, change.seat, ti.Zone.BATTLEFIELD)
            zone[index] = replace(seen, tapped=change.kind == "taps")
        elif change.kind == "ceases":
            zone, index, _ = self._find(change.item, change.seat, None)
            del zone[index]
        elif change.kind == "moves":
            zone, index, seen = self._find(change.item, None, change.from_zone)
            del zone[index]
            seat = seen.owner if change.seat is None else change.seat
            arrived = ti.Seen(seen.card, seat, False, seen.handle)
            if change.zone is ti.Zone.STACK:
                self._stack.insert(0, arrived)
            elif change.zone is ti.Zone.LIBRARY and change.value == "bottom":
                self._sides[seat]["library"].append(arrived)
            elif change.zone is ti.Zone.LIBRARY:
                self._sides[seat]["library"].insert(0, arrived)
            else:
                self._sides[seat][change.zone.value].append(arrived)

    def _find(self, item: Any, seat: int | None, zone: Any) -> tuple[list[Any], int, Any]:
        """The one zone list, index and object ``item`` names."""
        ti = _ti()
        places = []
        if zone is None or zone is ti.Zone.STACK:
            places.append(self._stack)
        for side_seat, side in enumerate(self._sides):
            if seat is not None and side_seat != seat:
                continue
            for name in _ZONES:
                if zone is None or zone.value == name:
                    places.append(side[name])
        found = []
        for place in places:
            for index, seen in enumerate(place):
                if (seen.handle == item) if isinstance(item, (ti.Handle, ti.Token)) else (seen.card is item):
                    found.append((place, index, seen))
        if not found:
            raise ScriptError(f"{_name(item)} is not on the board where the change looks for it")
        if len(found) > 1 and not isinstance(item, (ti.Handle, ti.Token)):
            if all(seen.card is found[0][2].card and seen.handle is None for _, _, seen in found):
                return found[0]
            raise ScriptError(f"more than one {_name(item)} could change; name it by handle or zone")
        return found[0]

    def _view(self) -> Any:
        ti = _ti()
        return ti.View(
            players=tuple(
                ti.PlayerView(
                    life=side["life"],
                    **{zone: tuple(side[zone]) for zone in _ZONES},
                )
                for side in self._sides
            ),
            stack=tuple(self._stack),
            step=_step(self._step),
            active=self._active,
            asked=None if self._over else self._asked,
            game_over=self._over,
            winner=self._winner,
        )


def _step(name: str) -> Any:
    ti = _ti()
    return ti.Phase[name] if name.endswith("_MAIN") else ti.Step[name]


def _name(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, type):
        return item.__name__
    return repr(item)


def _wants(entry: Any) -> str:
    parts = []
    for b in entry.branches:
        text = ", ".join(map(_name_preference, b.preferences)) or "nothing"
        if b.choices:
            text += f" (answering {', '.join(map(_name_preference, b.choices))})"
        for key, values in b.scoped:
            text += f" ({_name_preference(key)} at {', '.join(map(_name_preference, values))})"
        parts.append(text)
    return " or else ".join(parts)


def _name_preference(item: Any) -> str:
    if isinstance(item, type) or not hasattr(item, "attrs"):
        return _name(item)
    attrs = dict(item.attrs)
    if "seat" in attrs:
        return f"player {attrs['seat']}"
    printed = attrs.get("printed")
    return printed.__name__ if isinstance(printed, type) else repr(attrs)
