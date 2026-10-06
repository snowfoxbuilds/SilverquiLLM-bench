"""Card implementation for Embercleave."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment
from engine.continuous_effects import (
    DURATION_PERMANENT,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class EmbercleaveAbility1:
    text = 'Flash'


class EmbercleaveAbility2:
    text = 'This spell costs {1} less to cast for each attacking creature you control.'


class EmbercleaveAbility3:
    text = 'When Embercleave enters, attach it to target creature you control.'


class EmbercleaveAbility4:
    text = 'Equipped creature gets +1/+1 and has double strike and trample.'


class EmbercleaveAbility5:
    text = 'Equip {3}'


# endregion Printed abilities


class Embercleave(Equipment):
    """Embercleave — {4}{R}{R} — Legendary Artifact — Equipment.

    Flash
    This spell costs {1} less to cast for each attacking creature you control.
    When Embercleave enters the battlefield, attach it to target creature you
    control.
    Equipped creature gets +1/+1 and has double strike and trample.
    Equip {3}

    SPG collector number 77.
    """

    equip_printed = EmbercleaveAbility5

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Embercleave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{R}"))
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault(
            "rules_text",
            "Flash\n"
            "This spell costs {1} less to cast for each attacking creature you "
            "control.\n"
            "When Embercleave enters the battlefield, attach it to target "
            "creature you control.\n"
            "Equipped creature gets +1/+1 and has double strike and trample.\n"
            "Equip {3}",
        )
        kwargs.setdefault("equip_cost", ManaCost.parse("{3}"))
        super().__init__(**kwargs)

    def cost_reduction(self, game: "GameState") -> int:
        """This spell costs {1} less for each attacking creature you control."""
        controller = self.controller or self.owner
        if controller is None:
            return 0
        count = 0
        for perm in game.get_battlefield(controller).get_all():
            if CardType.CREATURE in getattr(perm, "card_types", set()) and getattr(
                perm, "is_attacking", False
            ):
                count += 1
        return count

    def make_equip_effects(self, game: "GameState") -> list[Any]:
        equipment = self

        def _pt(g: Any) -> None:
            if equipment.is_equip_active(g):
                creature = equipment.attached_to
                creature.modified_power += 1
                creature.modified_toughness += 1

        def _kw(g: Any) -> None:
            if equipment.is_equip_active(g):
                equipment.attached_to.keywords |= Keyword.DOUBLE_STRIKE | Keyword.TRAMPLE

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

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that targets as it is put
        on the stack (rule 603.3d)."""
        from engine.triggers import register_enters_trigger

        def _creature_you_control(game: Any, controller: Any) -> list[Any]:
            def _legal(obj: Any) -> bool:
                return CardType.CREATURE in getattr(obj, "card_types", set()) and getattr(obj, "controller", None) is controller

            return [TargetRequirement(filter_fn=_legal, description="target creature you control", zone=Zone.BATTLEFIELD)]

        register_enters_trigger(
            game, self, EmbercleaveAbility3, self._enters, targets=_creature_you_control, source_aware=True
        )

    def _enters(self, game: "GameState", targets: list[Any], controller: Any, source_remains: bool) -> None:
        """Attach to the target creature, if it is still a creature you control
        and this Equipment is still on the battlefield."""
        target = targets[0] if targets else None
        if target is not None and source_remains:
            self.equip(target, game)
