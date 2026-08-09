"""Card implementation for Mischievous Pup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


class MischievousPup(Creature):
    """Mischievous Pup — {2}{W} — 3/1 — Dog — Flash.

    When this creature enters, return up to one other target permanent you
    control to its owner's hand.

    FDN collector number 144.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mischievous Pup")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Dog"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash (You may cast this spell any time you could cast an "
            "instant.)\nWhen this creature enters, return up to one other "
            "target permanent you control to its owner's hand.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        """Up to one OTHER target permanent you control (optional/declinable)."""
        controller = self.controller or getattr(self, "owner", None)
        source = self

        def _filter(obj: Any) -> bool:
            return obj is not source and getattr(obj, "controller", None) is controller

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="up to one other target permanent you control",
                zone=Zone.BATTLEFIELD,
                optional=True,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Return the chosen permanent (if any) to its owner's hand."""
        from engine.zones import move_to_zone

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None or target is self:
            return
        if _on_battlefield(game, target):
            move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
