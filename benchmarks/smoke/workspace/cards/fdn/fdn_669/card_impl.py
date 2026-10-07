"""Card implementation for Basilisk Collar."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment
from engine.continuous_effects import DURATION_PERMANENT, ContinuousEffect, Layer
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BasiliskCollarAbility1:
    text = 'Equipped creature has deathtouch and lifelink. (Any amount of damage it deals to a creature is enough to destroy it. Damage dealt by this creature also causes you to gain that much life.)'


class BasiliskCollarAbility2:
    text = 'Equip {2} ({2}: Attach to target creature you control. Equip only as a sorcery.)'


# endregion Printed abilities


class BasiliskCollar(Equipment):
    """Basilisk Collar — {1} — Artifact — Equipment.

    Equipped creature has deathtouch and lifelink.
    Equip {2}

    FDN collector number 669.
    """

    equip_printed = BasiliskCollarAbility2

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Basilisk Collar")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "Equipped creature has deathtouch and lifelink.\nEquip {2}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{2}"))
        super().__init__(**kwargs)

    def make_equip_effects(self, game: GameState) -> list[Any]:
        equipment = self

        def _grant(g: Any) -> None:
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.keywords |= Keyword.DEATHTOUCH | Keyword.LIFELINK

        return [
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_grant,
                duration=DURATION_PERMANENT,
            ),
        ]
