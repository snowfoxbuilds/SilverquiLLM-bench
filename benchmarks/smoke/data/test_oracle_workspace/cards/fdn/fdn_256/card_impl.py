"""Card implementation for Meteor Golem."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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

    def _is_opponent_nonland_permanent(self, obj: Any) -> bool:
        """Legal target: a nonland permanent controlled by a player other than
        the caster. Shared by ``get_targets`` and the resolution revalidation."""
        controller = self.controller or getattr(self, "owner", None)
        if CardType.LAND in getattr(obj, "card_types", set()):
            return False
        obj_controller = getattr(obj, "controller", None)
        return obj_controller is not None and obj_controller is not controller

    def get_targets(self, game: "GameState") -> list[Any]:
        """Required target: a nonland permanent an opponent controls."""
        return [
            TargetRequirement(
                filter_fn=self._is_opponent_nonland_permanent,
                description="target nonland permanent an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Destroy the targeted permanent.

        Revalidate the COMPLETE predicate at resolution: still a *nonland*
        permanent an *opponent* controls, on the battlefield. If it became a
        land, came under the caster's control, or left play before resolution,
        it is illegal and is not destroyed.
        """
        from engine.game import destroy

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        if not _on_battlefield(game, target):
            return
        if not self._is_opponent_nonland_permanent(target):
            return
        destroy(game, target)
