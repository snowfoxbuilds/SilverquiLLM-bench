"""Card implementation for Meteor Golem."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class MeteorGolemAbility1:
    text = 'When this creature enters, destroy target nonland permanent an opponent controls.'


# endregion Printed abilities


def _on_battlefield(game: Any, obj: Any) -> bool:
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


class MeteorGolem(ArtifactCreature):
    """Meteor Golem — {7} — 3/3 — Golem.

    When this creature enters, destroy target nonland permanent an opponent
    controls.

    FDN collector number 256.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Meteor Golem")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("subtypes", {"Golem"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, destroy target nonland permanent an "
            "opponent controls.",
        )
        super().__init__(**kwargs)

    def _is_opponent_nonland_permanent(self, obj: Any, controller: Any) -> bool:
        """Legal target: a nonland permanent controlled by a player other than
        the ability's controller. Shared by the targeting and the resolution revalidation."""
        if CardType.LAND in getattr(obj, "card_types", set()):
            return False
        obj_controller = getattr(obj, "controller", None)
        return obj_controller is not None and obj_controller is not controller

    def _enters_targets(self, game: "GameState", controller: Any) -> list[Any]:
        """Required target: a nonland permanent an opponent controls."""
        return [
            TargetRequirement(
                filter_fn=lambda obj, _c=controller: self._is_opponent_nonland_permanent(obj, _c),
                description="target nonland permanent an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability: it targets as it is put
        on the stack (rule 603.3d)."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, MeteorGolemAbility1, self._enters, targets=self._enters_targets)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Destroy the targeted permanent.

        Revalidate the COMPLETE predicate at resolution: still a *nonland*
        permanent an *opponent* controls, on the battlefield. If it became a
        land, came under the caster's control, or left play before resolution,
        it is illegal and is not destroyed.
        """
        from engine.game import destroy

        target = targets[0] if targets else None
        if target is None:
            return
        if not _on_battlefield(game, target):
            return
        if not self._is_opponent_nonland_permanent(target, controller):
            return
        destroy(game, target)
