"""Card implementation for Celestial Armor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment, _obj_on_battlefield
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class CelestialArmor(Equipment):
    """Celestial Armor — {2}{W} — Artifact — Equipment — Flash.

    When this Equipment enters, attach it to target creature you control.
    That creature gains hexproof and indestructible until end of turn.
    Equipped creature gets +2/+0 and has flying.
    Equip {3}{W}

    FDN collector number 5.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Celestial Armor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Flash\n"
            "When this Equipment enters, attach it to target creature you "
            "control. That creature gains hexproof and indestructible until "
            "end of turn.\n"
            "Equipped creature gets +2/+0 and has flying.\n"
            "Equip {3}{W}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{3}{W}"))
        super().__init__(**kwargs)
        self.keywords = self.keywords | Keyword.FLASH

    def make_equip_effects(self, game: "GameState") -> list[Any]:
        equipment = self

        def _pt(g: Any) -> None:
            if equipment.is_equip_active(g):
                equipment.attached_to.modified_power += 2

        def _flying(g: Any) -> None:
            if equipment.is_equip_active(g):
                equipment.attached_to.keywords |= Keyword.FLYING

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
                apply=_flying,
                duration=DURATION_PERMANENT,
            ),
        ]

    def get_targets(self, game: "GameState") -> list[Any]:
        """Target creature you control (for the ETB attach)."""
        controller = self.controller or getattr(self, "owner", None)

        def _filter(obj: Any) -> bool:
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            return getattr(obj, "controller", None) is controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: attach to the chosen creature and grant it hexproof and
        indestructible until end of turn."""
        controller = self.controller
        if controller is None:
            return

        chosen = getattr(self, "chosen_targets", None)
        target_creature = chosen[0] if chosen else None
        if target_creature is None:
            return
        if not _obj_on_battlefield(game, target_creature):
            return
        if CardType.CREATURE not in getattr(target_creature, "card_types", set()):
            return
        if getattr(target_creature, "controller", None) is not controller:
            return

        self.equip(target_creature, game)

        protected_creature = target_creature

        def _apply_protection(g: Any) -> None:
            if _obj_on_battlefield(g, protected_creature):
                protected_creature.keywords |= Keyword.HEXPROOF | Keyword.INDESTRUCTIBLE

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply_protection,
                duration=DURATION_END_OF_TURN,
            )
        )
