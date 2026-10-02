"""Card implementation for Adventuring Gear."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class AdventuringGear(Equipment):
    """Adventuring Gear — {1} — Artifact — Equipment.

    Landfall — Whenever a land you control enters, equipped creature gets
    +2/+2 until end of turn.
    Equip {1}

    FDN collector number 249.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Adventuring Gear")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "Landfall — Whenever a land you control enters, equipped creature "
            "gets +2/+2 until end of turn.\nEquip {1}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    # Adventuring Gear has no static buff — its bonus is the landfall trigger.
    def make_equip_effects(self, game: "GameState") -> list[Any]:
        return []

    def register_triggers(self, game: "GameState") -> None:
        """Landfall: when a land you control enters, the equipped creature
        gets +2/+2 until end of turn."""
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            permanent = event.permanent
            if permanent is None:
                return False
            if CardType.LAND not in getattr(permanent, "card_types", set()):
                return False
            controller = getattr(source, "controller", None)
            perm_controller = event.controller or getattr(permanent, "controller", None)
            return controller is not None and perm_controller is controller

        def _effect(g: "GameState") -> None:
            if not source.is_equip_active(g):
                return
            creature = source.attached_to

            def _apply_landfall_pt(gg: Any) -> None:
                # Guard against the equipped creature changing before EOT.
                if source.is_equip_active(gg) and source.attached_to is creature:
                    creature.modified_power += 2
                    creature.modified_toughness += 2

            g.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_landfall_pt,
                    duration=DURATION_END_OF_TURN,
                )
            )

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
