"""Card implementation for Goldvein Pick."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.events import DealsDamageTriggeredEvent
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class GoldveinPickAbility1:
    text = 'Equipped creature gets +1/+1.'


class GoldveinPickAbility2:
    text = 'Whenever equipped creature deals combat damage to a player, create a Treasure token. (It\'s an artifact with "{T}, Sacrifice this token: Add one mana of any color.")'


class GoldveinPickAbility3:
    text = 'Equip {1} ({1}: Attach to target creature you control. Equip only as a sorcery.)'


# endregion Printed abilities


class GoldveinPick(Equipment):
    """Goldvein Pick — {2} — Artifact — Equipment.

    Equipped creature gets +1/+1.
    Whenever equipped creature deals combat damage to a player, create a
    Treasure token.
    Equip {1}

    FDN collector number 253.
    """

    equip_printed = GoldveinPickAbility3

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goldvein Pick")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault(
            "rules_text",
            "Equipped creature gets +1/+1.\n"
            "Whenever equipped creature deals combat damage to a player, "
            "create a Treasure token.\n"
            "Equip {1}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def make_equip_effects(self, game: "GameState") -> list[Any]:
        equipment = self

        def _pt(g: Any) -> None:
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.modified_power += 1
                creature.modified_toughness += 1

        return [
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_pt,
                duration=DURATION_PERMANENT,
            ),
        ]

    def register_triggers(self, game: "GameState") -> None:
        """Whenever the equipped creature deals combat damage to a player,
        create a Treasure token."""
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            creature = source.attached_to
            if creature is None:
                return False
            return (
                event.source is creature
                and hasattr(event.target, "life")
                and event.is_combat
            )

        def _effect(g: "GameState", controller: Any) -> None:
            from engine.game import create_token

            from cards.fdn.tokens import make_treasure_token

            if controller is None:
                return
            create_token(g, controller, make_treasure_token())

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DealsDamageTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
