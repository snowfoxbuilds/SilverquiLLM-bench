"""Card implementation for Plains."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Land, ManaAbility
from engine.types import ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class Plains(Land):
    """Plains — Basic Land. {T}: Add {W}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Plains")
        kwargs.setdefault("subtypes", {"Plains"})
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        def cost(game: "GameState") -> bool:
            if self.is_tapped:
                return False
            self.is_tapped = True
            return True

        def produce(game: "GameState") -> dict[ManaType, int]:
            return {ManaType.WHITE: 1}

        return [ManaAbility(cost=cost, mana_produced=produce, description="{T}: Add {W}.")]
