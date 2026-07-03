"""Card implementation for Thornfist Striker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ThornfistStriker(Creature):
    """Thornfist Striker — {2}{G} — 3/3 — Elf Druid.

    Ward {1}
    Infusion — Creatures you control get +1/+0 and have trample as long as
    you gained life this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thornfist Striker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        super().__init__(**kwargs)

    def _infusion_active(self) -> bool:
        """Check if infusion condition is met."""
        controller = self.controller
        return controller is not None and getattr(controller, "life_gained_this_turn", 0) > 0

    def provide_power_bonus(self, game: "GameState", creature: "Creature") -> int:
        """Grant +1/+0 to creatures controller controls if infusion active."""
        if creature.controller == self.controller and self._infusion_active():
            return 1
        return 0

    def provide_keywords(self, game: "GameState", creature: "Creature") -> Keyword:
        """Grant trample to creatures controller controls if infusion active."""
        if creature.controller == self.controller and self._infusion_active():
            return Keyword.TRAMPLE
        return Keyword(0)
