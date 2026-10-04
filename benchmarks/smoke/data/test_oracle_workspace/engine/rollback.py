"""Whole-game rollback for a rejected priority action (see ADR-017).

An engine may let a player choose an illegal action as long as it rejects it
with ``InvalidPlayerChoiceError`` and rolls the game back to the beginning of
the Priority Query in which the action began. :func:`take_snapshot` records the
shallow state of every mutable object reachable from the game — including the
cells and defaults of the closures card code registers — and
:meth:`GameSnapshot.restore` writes that state back *in place*, so every object
the test or the engine holds keeps its identity and objects created by the
rejected action simply become unreachable.

Decision-side state is not game state: a class lists the attributes a rollback
leaves alone in ``rollback_exempt`` (a player's intents and transcript, the refs
registry's monotonic id counter), so what the player saw and chose while the
rejected action ran survives the rollback.

Opaque builtin objects without ``__dict__`` or ``__slots__`` (iterators, a
``random.Random``'s internal state) are not captured.
"""

from __future__ import annotations

import enum
import types
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from engine import abilities

_ATOMIC = (
    type(None), bool, int, float, complex, str, bytes, range, type,
    types.ModuleType, types.BuiltinFunctionType, types.CodeType, enum.Enum,
)
_MISSING = object()


def _exempt(obj: Any) -> frozenset[str]:
    return getattr(type(obj), "rollback_exempt", frozenset())


def _slot_names(obj: Any) -> list[str]:
    names: list[str] = []
    for cls in type(obj).__mro__:
        slots = cls.__dict__.get("__slots__", ())
        names.extend([slots] if isinstance(slots, str) else slots)
    return [n for n in names if n not in ("__dict__", "__weakref__")]


@dataclass
class _Saved:
    obj: Any
    items: Any = None
    attrs: dict[str, Any] | None = None
    slots: dict[str, Any] = field(default_factory=dict)


def _capture(obj: Any) -> tuple[_Saved | None, list[Any]]:
    """The shallow state of ``obj`` and the objects it refers to."""
    if isinstance(obj, types.FunctionType):
        children = [cell for cell in obj.__closure__ or ()]
        children.extend(obj.__defaults__ or ())
        children.extend((obj.__kwdefaults__ or {}).values())
        return None, children
    if isinstance(obj, types.CellType):
        try:
            contents = obj.cell_contents
        except ValueError:
            return _Saved(obj, items=_MISSING), []
        return _Saved(obj, items=contents), [contents]
    if isinstance(obj, types.MethodType):
        return None, [obj.__self__, obj.__func__]
    if isinstance(obj, (tuple, frozenset)):
        return None, list(obj)

    saved = _Saved(obj)
    children: list[Any] = []
    if isinstance(obj, dict):
        saved.items = list(obj.items())
        children.extend(k for k, _ in saved.items)
        children.extend(v for _, v in saved.items)
    elif isinstance(obj, (list, set, deque, bytearray)):
        saved.items = list(obj)
        children.extend(saved.items)

    exempt = _exempt(obj)
    attrs = getattr(obj, "__dict__", None)
    if isinstance(attrs, dict):
        saved.attrs = {k: v for k, v in attrs.items() if k not in exempt}
        children.extend(saved.attrs.values())
    for name in _slot_names(obj):
        if name in exempt:
            continue
        value = getattr(obj, name, _MISSING)
        saved.slots[name] = value
        if value is not _MISSING:
            children.append(value)

    if saved.items is None and saved.attrs is None and not saved.slots:
        return None, children
    return saved, children


def _restore(saved: _Saved) -> None:
    obj = saved.obj
    if isinstance(obj, types.CellType):
        if saved.items is _MISSING:
            try:
                del obj.cell_contents
            except ValueError:
                pass
        else:
            obj.cell_contents = saved.items
        return
    if isinstance(obj, dict):
        dict.clear(obj)
        dict.update(obj, saved.items)
    elif isinstance(obj, list):
        list.__setitem__(obj, slice(None), saved.items)
    elif isinstance(obj, set):
        set.clear(obj)
        set.update(obj, saved.items)
    elif isinstance(obj, (deque, bytearray)):
        obj.clear()
        obj.extend(saved.items)
    if saved.attrs is not None:
        attrs = obj.__dict__
        kept = {k: attrs[k] for k in _exempt(obj) if k in attrs}
        attrs.clear()
        attrs.update(saved.attrs)
        attrs.update(kept)
    for name, value in saved.slots.items():
        if value is _MISSING:
            if hasattr(obj, name):
                object.__delattr__(obj, name)
        else:
            object.__setattr__(obj, name, value)


@dataclass
class GameSnapshot:
    """The recorded state of one game; :meth:`restore` puts it back in place."""

    _saved: list[_Saved]

    def restore(self) -> None:
        for saved in self._saved:
            _restore(saved)


def take_snapshot(game: Any) -> GameSnapshot:
    """Record the state of everything reachable from ``game``.

    Module-level engine state that a priority action can change (the
    loyalty-activated-this-turn tracker) is recorded too.
    """
    seen: set[int] = set()
    saved: list[_Saved] = []
    pending: list[Any] = [game, abilities._loyalty_activated_this_turn]
    while pending:
        obj = pending.pop()
        if isinstance(obj, _ATOMIC) or id(obj) in seen:
            continue
        seen.add(id(obj))
        record, children = _capture(obj)
        if record is not None:
            saved.append(record)
        pending.extend(children)
    return GameSnapshot(saved)
