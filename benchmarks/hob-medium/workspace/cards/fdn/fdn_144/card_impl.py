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

    def _is_other_permanent_you_control(self, obj: Any) -> bool:
        """Legal target: another permanent controlled by this card's controller
        (the caster). Shared by ``get_targets`` and the resolution revalidation."""
        controller = self.controller or getattr(self, "owner", None)
        return obj is not self and getattr(obj, "controller", None) is controller

    def get_targets(self, game: "GameState") -> list[Any]:
        """Up to one OTHER target permanent you control (optional/declinable)."""
        return [
            TargetRequirement(
                filter_fn=self._is_other_permanent_you_control,
                description="up to one other target permanent you control",
                zone=Zone.BATTLEFIELD,
                optional=True,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Return the chosen permanent (if any) to its owner's hand.

        Revalidate the COMPLETE predicate at resolution: still *another*
        permanent the caster controls, on the battlefield. A permanent whose
        control changed away from the caster before resolution is illegal and is
        not returned.
        """
        from engine.zones import move_to_zone

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        if not _on_battlefield(game, target):
            return
        if not self._is_other_permanent_you_control(target):
            return
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
