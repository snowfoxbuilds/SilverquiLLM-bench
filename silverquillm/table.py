"""Host-side helpers that write Audited Tests on the Test Interface.

A :class:`Table` follows the scripts a test writes, in the order the players
are asked, and fills in what the Test Interface needs from them: each entry's
expected view and its plain-English narration. The test states only what its
answers change on the board — a card moves, a token appears, a permanent taps,
a life total changes, the game ends — and the table works out the rest from
the rules: who is asked next (CR 117), the steps and turns that follow when
everyone passes, who declares attackers and blockers and whether the declare
blockers and combat damage steps happen (CR 508.8), the untap step and each
turn's draw from the known library. A test also states the turn's shape the
view cannot show: an extra turn, a first-strike combat damage step (CR 510.4)
or a trigger during cleanup (CR 514.3a).

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
    face: type | None = None

    def describe(self) -> str:
        name = _name(self.item)
        if self.kind == "moves":
            where = f"player {self.seat}'s " if self.seat is not None and self.zone.value != "stack" else ""
            place = "the stack" if self.zone.value == "stack" else f"{where}{self.zone.value}"
            position = " (bottom)" if self.value == "bottom" else ""
            as_face = f" as {_name(self.face)}" if self.face is not None else ""
            return f"{name} moves to {place}{as_face}{position}"
        if self.kind == "gains_control":
            return f"player {self.seat} gains control of {name}"
        if self.kind == "becomes":
            return f"{name} becomes {_name(self.value)}"
        if self.kind == "appears":
            return f"{name} appears on player {self.seat}'s battlefield"
        if self.kind == "ceases":
            return f"{name} leaves the game"
        if self.kind in ("taps", "untaps"):
            return f"{name} {'becomes tapped' if self.kind == 'taps' else 'untaps'}"
        if self.kind == "stays_tapped":
            return f"{name} stays tapped"
        if self.kind == "life":
            return f"player {self.seat}'s life becomes {self.value}"
        if self.kind == "shuffles":
            order = ", ".join(map(_name, self.value)) or "nothing"
            return f"player {self.seat}'s library is shuffled, top first: {order}"
        if self.kind == "on_stack":
            return f"{name} goes on the stack for player {self.seat}"
        if self.kind == "copied":
            return f"a copy of {name} goes on the stack for player {self.seat}"
        if self.kind == "cleanup_trigger":
            return f"in cleanup, {name} goes on the stack for player {self.seat}"
        if self.kind == "off_stack":
            return f"{name} leaves the stack"
        if self.kind == "first_strike_damage":
            return "a first-strike combat damage step will come first"
        if self.kind == "extra_turn":
            return f"player {self.seat} will take an extra turn after this one"
        if self.kind == "ends":
            return "the game ends in a draw" if self.seat is None else f"player {self.seat} wins the game"
        return self.kind


def moves(
    item: Any, to: Any, *, seat: int | None = None, from_zone: Any = None, bottom: bool = False,
    face: type | None = None,
) -> Change:
    """``item`` — a handle, or a class when only one such card could move —
    moves to zone ``to``; ``seat`` is the side it lands on — on the stack its
    controller, on the battlefield its controller, elsewhere its owner — by
    default the player who cast it for a spell resolving onto the
    battlefield and its owner otherwise; ``from_zone`` narrows where a class
    is looked for, and ``bottom`` puts it at the bottom of a library. A
    permanent keeps showing its owner whichever side it is on.

    ``face`` is the predefined face class a multi-face card is cast as: on the
    stack it shows as that face, and leaving the stack it shows as its card
    again (CR 715.3b, 715.4)."""
    return Change("moves", item, to, seat, from_zone, "bottom" if bottom else "top", face)


def gains_control(item: Any, seat: int) -> Change:
    """Player ``seat`` gains control of the permanent ``item``: it moves to
    their side of the battlefield, still owned and tapped as it was."""
    return Change("gains_control", item, seat=seat)


def becomes(item: Any, cls: type) -> Change:
    """The permanent ``item`` now shows as predefined class ``cls``, as a
    permanent that becomes a copy of another (CR 707.2) or stops being one
    does."""
    return Change("becomes", item, value=cls)


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


def stays_tapped(item: Any, seat: int | None = None) -> Change:
    """The tapped permanent ``item`` does not untap in the untap step the
    entry leads into, as a permanent that "doesn't untap" does (CR 502.3)."""
    return Change("stays_tapped", item, seat=seat)


def shuffles(seat: int, *order: Any) -> Change:
    """Player ``seat``'s library is shuffled into ``order``, top first — every
    card in it, each a handle or a class; the chance script states the same
    result."""
    return Change("shuffles", seat=seat, value=tuple(order))


def life(seat: int, total: int) -> Change:
    """Player ``seat``'s life total becomes ``total``."""
    return Change("life", seat=seat, value=total)


def on_stack(cls: type, seat: int) -> Change:
    """An ability of predefined class ``cls`` goes on the stack, controlled by
    ``seat``; it is put on top."""
    return Change("on_stack", cls, seat=seat)


def cleanup_trigger(cls: type, seat: int) -> Change:
    """An ability of predefined class ``cls`` triggers during the cleanup step
    that follows, controlled by ``seat``: players then receive priority in that
    cleanup step, and another cleanup step follows it (CR 514.3a)."""
    return Change("cleanup_trigger", cls, seat=seat)


def copied(cls: type, seat: int) -> Change:
    """A copy of a spell of class ``cls`` goes on top of the stack, controlled
    by ``seat``; spell copies are numbered in the order they are made."""
    return Change("copied", cls, seat=seat)


def off_stack(cls: type) -> Change:
    """The topmost stack object of class ``cls`` leaves the stack."""
    return Change("off_stack", cls)


def first_strike_damage() -> Change:
    """This combat has a first-strike combat damage step before the regular
    one, because an attacking or blocking creature has first or double strike
    (CR 510.4); stated before the declare blockers step ends."""
    return Change("first_strike_damage")


def extra_turn(seat: int) -> Change:
    """Player ``seat`` gets an extra turn after this one (CR 500.7): the
    table plays it next, the most recently created extra turn first, and
    then the normal turn order resumes."""
    return Change("extra_turn", seat=seat)


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
    "DECLARE_BLOCKERS", "FIRST_STRIKE_DAMAGE", "COMBAT_DAMAGE", "END_COMBAT", "POSTCOMBAT_MAIN", "END", "CLEANUP",
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
        # The owner of each card on the stack, which shows its controller.
        self._stack_owners: dict[int, int] = {}
        # The card class of each face on the stack, shown again once it leaves.
        self._stack_cards: dict[int, Any] = {}
        self._step = start.step.name
        self._active = start.active
        self._asked = start.asked
        self._turn = 1 if start.active == 0 else 2
        self._normal_next = 1 - start.active
        self._extra_turns: list[int] = []
        # Abilities that trigger in the coming cleanup step (CR 514.3a).
        self._cleanup_triggers: list[Any] = []
        self._passes = 0
        self._tokens = 0
        self._copies = 0
        # The declaration being asked ("attackers" or "blockers"), and whether
        # anything attacks this combat.
        self._declaring: str | None = None
        self._attacking = False
        self._declared_attack = False
        self._first_strike = False
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

    def act(
        self,
        seat: int,
        *preferences: Any,
        then: Iterable[Change] = (),
        note: str = "",
        attacks: bool | None = None,
        **options: Any,
    ) -> Any:
        """``seat`` takes an action; ``options`` are those of
        ``test_interface.act`` (``choices``, ``per_query``, ``distinct``,
        ``branches``). At a declare-attackers question, ``attacks`` says
        whether the declaration makes anything attack. The table works it out
        only when the entry settles it without asking the engine — every
        branch names creatures in its preferences, or none does; a
        ``per_query`` answer, a ``scoped`` answer with no creature named, or
        branches that mix a declaration with declaring nothing need the hint,
        and its absence is a ``ScriptError``."""
        if attacks is not None and self._declaring != "attackers":
            raise ScriptError("attacks= applies only to a declare-attackers question")
        entry = _ti().act(*preferences, **options)
        if self._declaring:
            if self._declaring == "attackers":
                if attacks is None:
                    attacks = _declares_something(entry)
                if attacks is None:
                    raise ScriptError(
                        "whether this declaration makes anything attack depends on the "
                        "engine's questions: say attacks=True or attacks=False"
                    )
                self._declared_attack = attacks
                if not attacks:
                    return self._write(seat, entry, then, note, "declares attackers: nothing")
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
            if change.kind != "stays_tapped":
                self._apply(change)
        self._derived = []
        if not self._over and self._declaring:
            if entry.kind is not ti.Kind.ILLEGAL:
                # The declaration is made — or declines — and the step's
                # priority window opens with the active player (CR 508.2, 509.2).
                if self._declaring == "attackers":
                    self._attacking = entry.kind is ti.Kind.ACT and self._declared_attack
                self._declaring = None
                self._asked = self._active
                self._passes = 0
        elif not self._over or entry.kind is ti.Kind.PASS:
            # A pass that ends the step also moves the game into the next one,
            # even when that step's turn-based actions — combat damage, a draw
            # from an empty library — end the game (CR 104.2a).
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
        for change in changes:
            if change.kind == "stays_tapped":
                # Applied over the untap step the table has just derived.
                self._apply(replace(change, kind="taps"))
        narration = f"Player {seat} {text}"
        said = (
            [c.describe() for c in changes if c.kind != "stays_tapped"]
            + self._derived
            + [c.describe() for c in changes if c.kind == "stays_tapped"]
        )
        if said:
            narration += "; " + "; ".join(said)
        entry = replace(entry, view=self._view(), note=note, narration=narration)
        self.scripts[seat].append(entry)
        return entry

    def _end_step(self) -> None:
        """The step ends: the game moves through the steps that follow, doing
        their turn-based actions, to the next one in which players receive
        priority (CR 500.2, 508.8).

        A cleanup step in which players received priority is followed by
        another cleanup step of the same turn (CR 514.3a): it takes that
        iteration's queued cleanup triggers, and the turn ends only after a
        cleanup step in which nothing triggered."""
        repeat_cleanup = self._step == "CLEANUP"
        while True:
            index = _TURN.index(self._step) + (0 if repeat_cleanup else 1)
            repeat_cleanup = False
            if index == len(_TURN):
                self._turn += 1
                if self._extra_turns:
                    self._active = self._extra_turns.pop()
                else:
                    self._active, self._normal_next = self._normal_next, 1 - self._normal_next
                index = 0
                self._derived.append(f"player {self._active}'s turn {self._turn} begins")
            self._step = _TURN[index]
            if self._step == "DECLARE_BLOCKERS" and not self._attacking:
                # Nothing was declared as an attacker (CR 508.8).
                self._step = "END_COMBAT"
            if self._step == "FIRST_STRIKE_DAMAGE" and not self._first_strike:
                # No first or double strike in this combat (CR 510.4).
                self._step = "COMBAT_DAMAGE"
            if self._step == "END_COMBAT":
                self._attacking = False
                self._first_strike = False
            if self._step in ("DECLARE_ATTACKERS", "DECLARE_BLOCKERS"):
                # The declaration is the step's turn-based action, asked of the
                # active player for attackers and the other for blockers.
                self._declaring = "attackers" if self._step == "DECLARE_ATTACKERS" else "blockers"
                self._asked = self._active if self._declaring == "attackers" else 1 - self._active
                self._derived.append(f"the game moves to {self._step.lower().replace('_', ' ')}")
                return
            if self._step == "CLEANUP" and self._cleanup_triggers:
                # Something triggered during cleanup: players receive priority
                # in it, and another cleanup step follows (CR 514.3a).
                for seen in self._cleanup_triggers:
                    self._stack.insert(0, seen)
                self._cleanup_triggers = []
                self._asked = self._active
                self._derived.append("the game moves to cleanup")
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
        elif change.kind == "first_strike_damage":
            self._first_strike = True
        elif change.kind == "extra_turn":
            self._extra_turns.append(change.seat)
        elif change.kind == "ends":
            self._over, self._winner = True, change.seat
        elif change.kind == "appears":
            self._tokens = max(self._tokens, change.item.number)
            self._sides[change.seat]["battlefield"].append(ti.Seen(None, change.seat, False, change.item))
        elif change.kind == "on_stack":
            self._stack.insert(0, ti.Seen(change.item, change.seat))
        elif change.kind == "copied":
            self._copies += 1
            self._stack.insert(0, ti.Seen(change.item, change.seat, False, ti.SpellCopy(self._copies)))
        elif change.kind == "cleanup_trigger":
            self._cleanup_triggers.append(ti.Seen(change.item, change.seat))
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
        elif change.kind == "shuffles":
            library = self._sides[change.seat]["library"]
            remaining = list(library)
            ordered = []
            for item in change.value:
                index = next(
                    (
                        i
                        for i, seen in enumerate(remaining)
                        if ((seen.handle == item) if isinstance(item, (ti.Handle, ti.Token)) else (seen.card is item))
                    ),
                    None,
                )
                if index is None:
                    raise ScriptError(f"{_name(item)} is not in player {change.seat}'s library to shuffle")
                ordered.append(remaining.pop(index))
            if remaining:
                raise ScriptError(f"a shuffle of player {change.seat}'s library leaves out {', '.join(map(repr, remaining))}")
            library[:] = ordered
        elif change.kind == "becomes":
            zone, index, seen = self._find(change.item, None, ti.Zone.BATTLEFIELD)
            zone[index] = replace(seen, card=change.value)
        elif change.kind == "gains_control":
            zone, index, seen = self._find(change.item, None, ti.Zone.BATTLEFIELD)
            del zone[index]
            self._sides[change.seat]["battlefield"].append(seen)
        elif change.kind == "moves":
            zone, index, seen = self._find(change.item, None, change.from_zone)
            del zone[index]
            from_stack = zone is self._stack
            owner = self._stack_owners.pop(id(seen), seen.owner) if from_stack else seen.owner
            if change.seat is not None:
                seat = change.seat
            elif from_stack and change.zone is ti.Zone.BATTLEFIELD:
                seat = seen.owner  # a resolving spell enters under its controller
            else:
                seat = owner
            shown = owner if change.zone is ti.Zone.BATTLEFIELD else seat
            cls = self._stack_cards.pop(id(seen), seen.card) if from_stack else seen.card
            arrived = ti.Seen(change.face or cls, shown, False, seen.handle)
            if change.zone is ti.Zone.STACK:
                self._stack.insert(0, arrived)
                self._stack_owners[id(arrived)] = owner
                if change.face is not None:
                    self._stack_cards[id(arrived)] = cls
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


def _declares_something(entry: Any) -> bool | None:
    """Whether a declaration entry makes something attack, when the entry
    alone settles it: ``True`` when every branch names creatures in its
    preferences, ``False`` when none does, and ``None`` when the outcome
    depends on what the engine offers — a branch with ``per_query`` answers
    or ``scoped`` answers but no creature named, or branches that mix a
    declaration with declaring nothing."""
    outcomes = set()
    for b in entry.branches:
        if b.per_query or (b.scoped and not b.preferences):
            return None
        outcomes.add(bool(b.preferences))
    return outcomes.pop() if len(outcomes) == 1 else None


def _wants(entry: Any) -> str:
    parts = []
    for b in entry.branches:
        text = ", ".join(map(_name_preference, b.preferences))
        if b.per_query:
            asked = "; ".join(", ".join(map(_name_preference, prefs)) or "nothing" for _, prefs in b.per_query)
            text = ", ".join(filter(None, [text, f"per question: {asked}"]))
        text = text or "nothing"
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
