"""Card implementation for Foolish Fate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import LosesLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class FoolishFate(Instant):
    """Foolish Fate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Foolish Fate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Destroy target creature.\nInfusion — If you gained life this turn, that creature's "
            "controller loses 3 life.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if not isinstance(target, Creature):
            return

        controller = getattr(target, "controller", None)
        if controller is None or not game.get_battlefield(controller).contains(target):
            return

        destroy(game, target)

        spell_controller = self.controller
        if spell_controller is None or getattr(spell_controller, "life_gained_this_turn", 0) <= 0:
            return

        controller.life -= 3
        game.trigger_manager.fire_event(game, LosesLifeTriggeredEvent(player=controller, amount=3))
