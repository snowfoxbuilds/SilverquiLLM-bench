"""Pytest plugin for ``made_object_label_checks.py``: the engine numbers the
tokens and spell copies it makes in another order — each window's in reverse,
with an object no view ever shows numbered before each — as an engine may
that makes several at once in its own order, or numbers copies it never casts."""

from __future__ import annotations

import pytest


class _Unseen:
    """A made object no zone ever holds."""


class _Renumbering(list):
    def append(self, item):
        # Ahead of everything made earlier: the interface numbers only what
        # it has not numbered yet, so this reverses each window's order.
        self.insert(0, item)
        self.insert(0, _Unseen())


def renumber_made(monkeypatch: pytest.MonkeyPatch) -> None:
    import engine.game_state

    original = engine.game_state.GameState.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.created_tokens = _Renumbering(self.created_tokens)
        self.created_copies = _Renumbering(self.created_copies)

    monkeypatch.setattr(engine.game_state.GameState, "__init__", init)


@pytest.fixture(autouse=True)
def _made_objects_renumbered(monkeypatch):
    renumber_made(monkeypatch)
