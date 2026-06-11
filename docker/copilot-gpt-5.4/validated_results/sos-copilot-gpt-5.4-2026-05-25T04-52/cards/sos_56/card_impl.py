"""Card implementation for Landscape Painter // Vibrant Idea."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost


class VibrantIdea(Sorcery):
    """Prepared spell copy for Landscape Painter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vibrant Idea")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)


class LandscapePainterVibrantIdea(Creature):
    """Landscape Painter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Landscape Painter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Wizard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return VibrantIdea(owner=self.owner, controller=self.controller)
