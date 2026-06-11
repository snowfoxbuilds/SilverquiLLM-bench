"""Card implementation for Harmonized Trio // Brainstorm."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class HarmonizedTrioBrainstorm(Creature):
    """Harmonized Trio // Brainstorm — {U} Creature — Merfolk Bard Wizard 1/1.

    {T}, Tap two untapped creatures you control: This creature becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Harmonized Trio")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Bard", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        def cost(game: "GameState") -> bool:
            if self.is_tapped:
                return False
            self.is_tapped = True
            controller = self.controller
            bf = game.get_battlefield(controller)
            untapped = [
                c for c in bf
                if c is not self
                and CardType.CREATURE in getattr(c, "card_types", set())
                and not getattr(c, "is_tapped", True)
            ]
            if len(untapped) < 2:
                return False
            untapped[0].is_tapped = True
            untapped[1].is_tapped = True
            return True

        def effect(game: "GameState") -> None:
            self.is_prepared = True

        return [
            ActivatedAbility(
                cost=cost,
                effect=effect,
                description="{T}, Tap two untapped creatures you control: This creature becomes prepared.",
            )
        ]
