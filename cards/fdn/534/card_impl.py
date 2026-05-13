"""Card implementation for CarnelianOrbOfDragonkind."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class CarnelianOrbOfDragonkind(Artifact):
    """Carnelian Orb of Dragonkind — {2}{R} — {T}: Add {R}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Carnelian Orb of Dragonkind")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {R}. If that mana is spent on a Dragon creature spell, "
            "it gains haste until end of turn.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add {R}."),
        ]


__all__ = ["CarnelianOrbOfDragonkind"]
