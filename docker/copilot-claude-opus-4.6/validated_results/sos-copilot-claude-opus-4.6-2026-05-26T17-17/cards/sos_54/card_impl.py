"""Card implementation for Hydro-Channeler."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class HydroChanneler(Creature):
    """Hydro-Channeler — {1}{U} Creature — Merfolk Wizard 1/3.

    {T}: Add {U}. Spend this mana only to cast an instant or sorcery spell.
    {1}, {T}: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hydro-Channeler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Wizard"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        def cost1(game: "GameState") -> bool:
            if self.is_tapped:
                return False
            self.is_tapped = True
            return True

        def effect1(game: "GameState") -> None:
            controller = self.controller
            controller.mana_pool.add(ManaType.BLUE, 1)

        def cost2(game: "GameState") -> bool:
            if self.is_tapped:
                return False
            controller = self.controller
            # Pay {1} generic
            pool = controller.mana_pool
            paid = False
            for mt in ManaType:
                if pool.get(mt) >= 1:
                    pool._pool[mt] -= 1
                    paid = True
                    break
            if not paid:
                return False
            self.is_tapped = True
            return True

        def effect2(game: "GameState") -> None:
            controller = self.controller
            controller.mana_pool.add(ManaType.BLUE, 1)

        return [
            ActivatedAbility(
                cost=cost1,
                effect=effect1,
                description="{T}: Add {U}. Spend this mana only to cast an instant or sorcery spell.",
            ),
            ActivatedAbility(
                cost=cost2,
                effect=effect2,
                description="{1}, {T}: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]
