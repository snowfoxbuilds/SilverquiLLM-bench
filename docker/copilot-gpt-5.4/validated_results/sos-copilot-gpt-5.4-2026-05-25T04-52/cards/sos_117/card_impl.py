"""Card implementation for Goblin Glasswright // Craft with Pride."""

from __future__ import annotations
from typing import Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost


class CraftWithPride(Sorcery):
    """Prepared spell copy for Goblin Glasswright."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Craft with Pride")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)



class GoblinGlasswrightCraftWithPride(Creature):
    """Goblin Glasswright."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Glasswright")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Sorcerer"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def on_resolve(self, game: object) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Sorcery:
        return CraftWithPride(owner=self.owner, controller=self.controller)
