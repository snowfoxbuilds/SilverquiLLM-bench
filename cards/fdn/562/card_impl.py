"""Card implementation for GoblinFirebomb."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class GoblinFirebomb(Artifact):
    """Goblin Firebomb — {1} — Flash. {7}, {T}, Sacrifice: Destroy target permanent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Firebomb")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault(
            "rules_text",
            "Flash\n{7}, {T}, Sacrifice this artifact: Destroy target permanent.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import destroy
            target = getattr(source, "_resolve_target", None)
            if target is not None:
                destroy(game, target)

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{7}, {T}, Sacrifice: Destroy target permanent.",
            ),
        ]


__all__ = ["GoblinFirebomb"]
