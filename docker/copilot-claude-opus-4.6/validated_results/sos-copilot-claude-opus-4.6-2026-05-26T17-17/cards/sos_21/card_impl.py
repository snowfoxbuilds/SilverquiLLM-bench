"""Card implementation for Inkshape Demonstrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class InkshapeDemonstrator(Creature):
    """Inkshape Demonstrator — {3}{W} — 3/4 Elephant Cleric.

    Ward {2}
    Repartee — Whenever you cast an instant or sorcery spell that targets
    a creature, this creature gets +1/+0 and gains lifelink until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inkshape Demonstrator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}"))
        kwargs.setdefault("subtypes", {"Elephant", "Cleric"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.ward_cost: ManaCost = ManaCost.parse("{2}")
        self._repartee_power_bonus: int = 0

    def get_power(self, game: "GameState") -> int:
        """Return current power including repartee bonus."""
        return self.power + self._repartee_power_bonus

    def on_repartee_trigger(self, game: "GameState", target: Any) -> None:
        """Fire the repartee trigger: +1/+0 and lifelink until end of turn."""
        self._repartee_power_bonus += 1
        self.keywords = self.keywords | Keyword.LIFELINK
