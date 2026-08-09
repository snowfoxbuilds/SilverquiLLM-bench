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

    def get_targets(self, game: "GameState") -> list[Any]:
        """Required target: a nonland permanent an opponent controls."""
        controller = self.controller or getattr(self, "owner", None)

        def _filter(obj: Any) -> bool:
            if CardType.LAND in getattr(obj, "card_types", set()):
                return False
            return getattr(obj, "controller", None) is not controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target nonland permanent an opponent controls",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Destroy the targeted permanent."""
        from engine.game import destroy

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        if _on_battlefield(game, target):
            destroy(game, target)
