"""Card implementation for Mischievous Pup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class MischievousPupAbility1:
    text = 'Flash (You may cast this spell any time you could cast an instant.)'


class MischievousPupAbility2:
    text = "When this creature enters, return up to one other target permanent you control to its owner's hand."


# endregion Printed abilities


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
        (the ability's controller). Shared by the targeting and the resolution revalidation."""
        controller = self.controller or getattr(self, "owner", None)
        return obj is not self and getattr(obj, "controller", None) is controller

    def _enters_targets(self, game: "GameState", controller: Any) -> list[Any]:
        """Up to one OTHER target permanent you control (optional/declinable)."""
        return [
            TargetRequirement(
                filter_fn=self._is_other_permanent_you_control,
                description="up to one other target permanent you control",
                zone=Zone.BATTLEFIELD,
                optional=True,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability: it targets as it is put
        on the stack (rule 603.3d)."""
        from engine.triggers import register_enters_trigger

        register_enters_trigger(game, self, MischievousPupAbility2, self._enters, targets=self._enters_targets)

    def _enters(self, game: "GameState", targets: list[Any], controller: Any) -> None:
        """Return the chosen permanent (if any) to its owner's hand.

        Revalidate the COMPLETE predicate at resolution: still *another*
        permanent the caster controls, on the battlefield. A permanent whose
        control changed away from the caster before resolution is illegal and is
        not returned.
        """
        from engine.zones import move_to_zone

        target = targets[0] if targets else None
        if target is None:
            return
        if not _on_battlefield(game, target):
            return
        if not self._is_other_permanent_you_control(target):
            return
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)
