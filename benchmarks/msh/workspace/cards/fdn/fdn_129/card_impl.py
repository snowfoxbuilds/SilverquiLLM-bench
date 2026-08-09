"""Card implementation for Leyline Axe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class LeylineAxe(Equipment):
    """Leyline Axe — {4} — Artifact — Equipment.

    Equipped creature gets +1/+1 and has double strike and trample.
    Equip {3}

    FDN collector number 129.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Leyline Axe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault(
            "rules_text",
            "If this card is in your opening hand, you may begin the game "
            "with it on the battlefield.\n"
            "Equipped creature gets +1/+1 and has double strike and trample.\n"
            "Equip {3}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def make_equip_effects(self, game: "GameState") -> list[Any]:
        equipment = self

        def _pt(g: Any) -> None:
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.modified_power += 1
                creature.modified_toughness += 1

        def _kw(g: Any) -> None:
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.keywords |= Keyword.DOUBLE_STRIKE | Keyword.TRAMPLE

        return [
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_pt,
                duration=DURATION_PERMANENT,
            ),
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_kw,
                duration=DURATION_PERMANENT,
            ),
        ]
