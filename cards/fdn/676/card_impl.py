"""Card implementation for MazemindTome."""

from __future__ import annotations


from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype
from typing import TYPE_CHECKING, Any



class MazemindTome(Artifact):
    """Mazemind Tome — {2} — Scry/draw with page counters; exile at 4 counters."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mazemind Tome")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Book"}
        kwargs.setdefault(
            "rules_text",
            "{T}, Put a page counter on this artifact: Scry 1.\n"
            "{2}, {T}, Put a page counter on this artifact: Draw a card.\n"
            "When there are four or more page counters on this artifact, exile it. "
            "If you do, you gain 4 life.",
        )
        super().__init__(**kwargs)
        self.page_counters: int = 0

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _scry_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _scry_effect(game: Any) -> None:
            source.page_counters += 1
            # Scry 1: simplified — no-op (would need library peek)
            if source.page_counters >= 4:
                from engine.game import exile
                controller = source.controller
                if controller is not None:
                    controller.life += 4
                exile(game, source)

        def _draw_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _draw_effect(game: Any) -> None:
            from engine.game import draw_card
            source.page_counters += 1
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)
            if source.page_counters >= 4:
                from engine.game import exile
                controller = source.controller
                if controller is not None:
                    controller.life += 4
                exile(game, source)

        return [
            ActivatedAbility(
                cost=_scry_cost, effect=_scry_effect,
                description="{T}, Put a page counter: Scry 1.",
            ),
            ActivatedAbility(
                cost=_draw_cost, effect=_draw_effect,
                description="{2}, {T}, Put a page counter: Draw a card.",
            ),
        ]


__all__ = ["MazemindTome"]
