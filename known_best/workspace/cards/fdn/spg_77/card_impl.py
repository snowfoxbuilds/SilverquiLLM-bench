"""Card implementation for Embercleave."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Equipment
from engine.card_queries import choose_object
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


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

    def on_resolve(self, game: "GameState") -> None:
        """ETB: attach to a creature you control (chosen via Player Query)."""
        controller = self.controller or self.owner
        if controller is None:
            return
        creatures = [
            obj
            for obj in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        ]
        if not creatures:
            return
        target = choose_object(
            game,
            controller,
            creatures,
            "Choose a creature to attach Embercleave to",
            source_card=self,
        )
        if target is not None:
            self.equip(target, game)
