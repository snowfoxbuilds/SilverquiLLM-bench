"""Card implementation for PyromancersGoggles."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class PyromancersGoggles(Artifact):
    """Pyromancer's Goggles — {5} — Legendary — {T}: Add {R}. Copy effect."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pyromancer's Goggles")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {R}. When that mana is spent to cast a red instant or sorcery "
            "spell, copy that spell and you may choose new targets for the copy.",
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


__all__ = ["PyromancersGoggles"]
