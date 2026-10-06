"""Card implementation for Swiftfoot Boots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SwiftfootBootsAbility1:
    text = "Equipped creature has hexproof and haste. (It can't be the target of spells or abilities your opponents control. It can attack and {T} no matter when it came under your control.)"


class SwiftfootBootsAbility2:
    text = 'Equip {1} ({1}: Attach to target creature you control. Equip only as a sorcery.)'


# endregion Printed abilities


class SwiftfootBoots(Equipment):
    """Swiftfoot Boots — {2} — Artifact — Equipment.

    Equipped creature has hexproof and haste.
    Equip {1}

    FDN collector number 258.
    """

    equip_printed = SwiftfootBootsAbility2

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swiftfoot Boots")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault(
            "rules_text",
            "Equipped creature has hexproof and haste.\nEquip {1}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def make_equip_effects(self, game: "GameState") -> list[Any]:
        equipment = self

        def _kw(g: Any) -> None:
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.keywords |= Keyword.HEXPROOF | Keyword.HASTE

        return [
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_kw,
                duration=DURATION_PERMANENT,
            ),
        ]
