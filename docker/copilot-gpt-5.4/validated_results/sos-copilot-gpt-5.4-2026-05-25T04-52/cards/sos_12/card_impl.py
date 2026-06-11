"""Card implementation for Elite Interceptor // Rejoinder."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost


class Rejoinder(Sorcery):
    """Prepared spell copy for Elite Interceptor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rejoinder")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("rules_text", "Prepared spell copy.")
        super().__init__(**kwargs)


class EliteInterceptorRejoinder(Creature):
    """Elite Interceptor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Elite Interceptor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "This creature enters prepared. (While it's prepared, you may cast a copy of its spell. "
            "Doing so unprepares it.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return Rejoinder(owner=self.owner, controller=self.controller)
