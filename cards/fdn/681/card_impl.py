"""Card implementation for SteelHellkite."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class SteelHellkite(ArtifactCreature):
    """Steel Hellkite — {6} — 5/5 Dragon. Flying. {2}: +1/+0.
    {X}: Destroy each nonland permanent with mana value X."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Steel Hellkite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault(
            "rules_text",
            "Flying\n"
            "{2}: This creature gets +1/+0 until end of turn.\n"
            "{X}: Destroy each nonland permanent with mana value X whose controller "
            "was dealt combat damage by this creature this turn. Activate only once each turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pump_cost(game: Any, src: Any) -> bool:
            return True  # Mana payment not modelled

        def _pump_effect(game: Any) -> None:
            source.base_power += 1

        return [
            ActivatedAbility(
                cost=_pump_cost, effect=_pump_effect,
                description="{2}: +1/+0 until end of turn.",
            ),
        ]


__all__ = ["SteelHellkite"]
