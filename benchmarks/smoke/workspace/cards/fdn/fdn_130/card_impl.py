"""Card implementation for Quick-Draw Katana."""

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


class QuickDrawKatana(Equipment):
    """Quick-Draw Katana — {2} — Artifact — Equipment.

    During your turn, equipped creature gets +2/+0 and has first strike.
    Equip {2}

    FDN collector number 130.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Quick-Draw Katana")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault(
            "rules_text",
            "During your turn, equipped creature gets +2/+0 and has first "
            "strike.\nEquip {2}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def make_equip_effects(self, game: "GameState") -> list[Any]:
        equipment = self

        def _on_controllers_turn(g: Any) -> bool:
            controller = equipment.controller
            return controller is not None and getattr(g, "active_player", None) is controller

        def _pt(g: Any) -> None:
            if equipment.is_equip_active(g) and _on_controllers_turn(g):
                equipment.attached_to.modified_power += 2

        def _kw(g: Any) -> None:
            if equipment.is_equip_active(g) and _on_controllers_turn(g):
                equipment.attached_to.keywords |= Keyword.FIRST_STRIKE

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
