"""Card implementation for Growth Curve."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GrowthCurve(Sorcery):
    """Growth Curve — {G}{U} — Sorcery.

    Put a +1/+1 counter on target creature you control, then double the number
    of +1/+1 counters on that creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Growth Curve")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        """Target creature you control."""
        controller = self.controller

        def _filter(obj: Any) -> bool:
            card_types = getattr(obj, "card_types", set())
            if CardType.CREATURE not in card_types:
                return False
            # Must be controlled by the spell's controller
            if controller is not None:
                return getattr(obj, "controller", None) is controller
            return True

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Put a +1/+1 counter, then double +1/+1 counters."""
        chosen = getattr(self, "chosen_targets", [])
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        # Put a +1/+1 counter
        target.plus_one_counters += 1
        target._base_plus_one_counters = target.plus_one_counters

        # Then double the number of +1/+1 counters
        target.plus_one_counters *= 2
        target._base_plus_one_counters = target.plus_one_counters
