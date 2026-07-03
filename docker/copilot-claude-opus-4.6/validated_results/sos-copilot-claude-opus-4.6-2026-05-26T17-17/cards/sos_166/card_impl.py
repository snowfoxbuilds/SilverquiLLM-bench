"""Card implementation for Vastlands Scavenger // Bind to Life."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class VastlandsScavengerBindToLife(Creature):
    """Vastlands Scavenger // Bind to Life — {1}{G}{G} // {4}{G}.

    Creature — Bear Druid — 4/4. Deathtouch.
    This creature enters prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vastlands Scavenger")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}{G}"))
        kwargs.setdefault("subtypes", {"Bear", "Druid"})
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH | Keyword.PREPARED)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.prepared: bool = False
        self.spell_name: str = "Bind to Life"
        self.spell_mana_cost: ManaCost = ManaCost.parse("{4}{G}")

    def on_enter_battlefield(self, game: "GameState") -> None:
        """This creature enters prepared."""
        self.prepared = True

    def can_cast_prepared_spell(self, game: "GameState") -> bool:
        """Check if the prepared spell can be cast."""
        return self.prepared is True

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Bind to Life, unpreparing this creature."""
        if not self.prepared:
            return
        self.prepared = False
