"""Card implementation for Dig Site Inventory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DigSiteInventory(Sorcery):
    """Dig Site Inventory."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dig Site Inventory")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Put a +1/+1 counter on target creature you control. It gains vigilance "
            "until end of turn.\nFlashback {W}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{W}")

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature)
                and getattr(obj, "controller", None) is self.controller,
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if target is None:
            return
        if not isinstance(target, Creature):
            return
        if self.controller is None:
            return
        if getattr(target, "controller", None) is not self.controller:
            return
        if not game.get_battlefield(self.controller).contains(target):
            return

        target.plus_one_counters += 1
        if hasattr(target, "_base_plus_one_counters"):
            target._base_plus_one_counters = target.plus_one_counters

        def _apply(game: GameState) -> None:
            target.keywords |= Keyword.VIGILANCE

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            )
        )
        game.effect_manager.apply_all(game)
