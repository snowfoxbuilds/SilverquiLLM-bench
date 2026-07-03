"""Card implementation for Blazing Firesinger // Seething Song."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.mana import ManaType
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class SeethingSong(Instant):
    """Prepared spell copy for Blazing Firesinger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Seething Song")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("rules_text", "Add {R}{R}{R}{R}{R}.")
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        controller.mana_pool.add(ManaType.RED, 5)


class BlazingFiresingerSeethingSong(Creature):
    """Blazing Firesinger."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blazing Firesinger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("subtypes", {"Dwarf", "Bard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "This creature enters prepared. (While it's prepared, you may cast a copy of its spell. "
            "Doing so unprepares it.)",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:  # noqa: ARG002
        self.become_prepared()

    def create_prepared_spell_copy(self) -> Instant:
        return SeethingSong(owner=self.owner, controller=self.controller)
