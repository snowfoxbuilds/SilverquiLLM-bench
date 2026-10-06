"""Pytest plugin for ``reversed_option_checks.py``: every question reaches the
scripted player with its options in reverse order, a stable order an engine
may equally choose (ADR-017)."""

from __future__ import annotations

from dataclasses import replace

import pytest


def reverse_options(monkeypatch: pytest.MonkeyPatch) -> None:
    import test_interface

    original = test_interface.ScriptedPlayer.answer

    def answer(self, query):
        return original(self, replace(query, options=tuple(reversed(query.options))))

    monkeypatch.setattr(test_interface.ScriptedPlayer, "answer", answer)


@pytest.fixture(autouse=True)
def _every_question_reversed(monkeypatch):
    reverse_options(monkeypatch)
