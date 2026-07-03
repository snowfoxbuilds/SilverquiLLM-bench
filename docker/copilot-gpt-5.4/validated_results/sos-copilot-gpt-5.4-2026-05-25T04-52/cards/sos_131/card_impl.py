"""Card implementation for Strife Scholar // Awaken the Ages."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost


class AwakenTheAges(Sorcery):
    """Prepared spell copy for Strife Scholar."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Awaken the Ages")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}"))
        super().__init__(**kwargs)


class StrifeScholarAwakenTheAges(Creature):
    """Strife Scholar."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Strife Scholar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("subtypes", {"Orc", "Sorcerer"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)
        self.ward_cost = 2

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return AwakenTheAges(owner=self.owner, controller=self.controller)
