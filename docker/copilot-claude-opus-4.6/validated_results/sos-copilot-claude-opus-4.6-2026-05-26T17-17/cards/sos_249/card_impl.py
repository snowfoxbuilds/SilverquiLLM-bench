"""Card implementation for Mage Tower Referee."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class MageTowerReferee(ArtifactCreature):
    """Mage Tower Referee — {2} — 2/1 Artifact Creature — Construct.

    Whenever you cast a multicolored spell, put a +1/+1 counter on this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mage Tower Referee")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", {"Construct"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", spell_colors: list[str] | None = None) -> None:
        """Trigger: add +1/+1 counter when controller casts a multicolored spell."""
        if spell_colors and len(spell_colors) >= 2:
            self.plus_one_counters += 1
