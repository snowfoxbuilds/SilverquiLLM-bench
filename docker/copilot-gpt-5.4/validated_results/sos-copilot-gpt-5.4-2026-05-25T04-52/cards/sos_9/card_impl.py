"""Card implementation for Daydream."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Daydream(Sorcery):
    """Daydream."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Daydream")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature you control, then return that card to the battlefield "
            "under its owner's control with a +1/+1 counter on it.\nFlashback {2}{W}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{2}{W}")

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

        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)
        if target.owner is not None:
            target.controller = target.owner
        move_to_zone(game, target, Zone.EXILE, Zone.BATTLEFIELD)
        target.plus_one_counters += 1
        if hasattr(target, "_base_plus_one_counters"):
            target._base_plus_one_counters = target.plus_one_counters
