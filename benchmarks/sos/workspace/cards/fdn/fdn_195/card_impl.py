"""Card implementation for Fanatical Firebrand."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class FanaticalFirebrand(Creature):
    """Fanatical Firebrand — {R} — 1/1 — Goblin Pirate

    Haste
    {T}, Sacrifice this creature: It deals 1 damage to any target.

    FDN collector number 195.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fanatical Firebrand")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Pirate"})
        kwargs.setdefault("keywords", Keyword.HASTE)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Haste\n{T}, Sacrifice this creature: It deals 1 damage to "
            "any target.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            # Sacrifice self
            controller = src.controller
            if controller is None:
                return False
            from engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            from engine.game import deal_damage

            target = getattr(source, "_current_target", None)
            if target is not None:
                deal_damage(game, source, target, 1)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{T}, Sacrifice this creature: It deals 1 damage "
            "to any target.",
        )]
