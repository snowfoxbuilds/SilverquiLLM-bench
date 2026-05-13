"""Card implementation for RamosDragonEngine."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class RamosDragonEngine(ArtifactCreature):
    """Ramos, Dragon Engine — {6} — Legendary 4/4 Dragon. Flying.
    Spell cast → counters. Remove 5 counters → add WUBRG×2."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ramos, Dragon Engine")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhenever you cast a spell, put a +1/+1 counter on Ramos for "
            "each of that spell's colors.\nRemove five +1/+1 counters from Ramos: "
            "Add {W}{W}{U}{U}{B}{B}{R}{R}{G}{G}. Activate only once each turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            counters = getattr(source, "plus_one_counters", 0)
            if counters < 5:
                return False
            source.plus_one_counters -= 5
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.WHITE, 2)
                controller.mana_pool.add(ManaType.BLUE, 2)
                controller.mana_pool.add(ManaType.BLACK, 2)
                controller.mana_pool.add(ManaType.RED, 2)
                controller.mana_pool.add(ManaType.GREEN, 2)

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="Remove five +1/+1 counters: Add {W}{W}{U}{U}{B}{B}{R}{R}{G}{G}.",
            ),
        ]


__all__ = ["RamosDragonEngine"]
