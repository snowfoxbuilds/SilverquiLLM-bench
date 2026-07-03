"""Card implementation for Adventurous Eater // Have a Bite."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost


class HaveABite(Sorcery):
    """Prepared spell copy for Adventurous Eater."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Have a Bite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}"))
        super().__init__(**kwargs)


class AdventurousEaterHaveABite(Creature):
    """Adventurous Eater."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Adventurous Eater")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Human", "Warlock"})
        kwargs.setdefault("base_power", 3)
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
        return HaveABite(owner=self.owner, controller=self.controller)
