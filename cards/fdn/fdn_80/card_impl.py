"""Card implementation for Bulk Up."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BulkUp(Instant):
    """Bulk Up — {1}{ Instant.R} 

    Double target creature's power until end of turn.
    Flashback {4}{R}{R}

    FDN collector number 80.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bulk Up")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Double target creature's power until end of turn.\n"
            "Flashback {4}{R}{R}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{4}{R}{R}")

    def get_targets(self, game: "GameState") -> list:
        """Target creature."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Double target creature's power until end of turn."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        # Verify still a creature on the battlefield
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return

        # Snapshot current power (includes counters/buffs), not base_power.
        current_power = target.power

        def _apply(game: Any) -> None:
            target.base_power += current_power

        game.effect_manager.add(ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_END_OF_TURN,
        ))
