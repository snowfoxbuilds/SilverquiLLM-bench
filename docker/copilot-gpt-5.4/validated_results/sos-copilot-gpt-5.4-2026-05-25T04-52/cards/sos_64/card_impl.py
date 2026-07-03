"""Card implementation for Procrastinate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.game import add_counter, tap
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class Procrastinate(Sorcery):
    """Procrastinate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Procrastinate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Tap target creature. Put twice X stun counters on it.",
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
        target = self.chosen_targets[0] if getattr(self, "chosen_targets", []) else None
        if not isinstance(target, Creature):
            return
        controller = self.controller if self.controller is not None else getattr(target, "controller", None)
        if not target.is_on_battlefield(game) and (
            controller is None or not game.is_fresh_setup_sandbox(controller)
        ):
            return
        tap(game, target)
        x_value = max(0, int(getattr(self, "x_value", 0)))
        if x_value > 0:
            add_counter(game, target, "stun", amount=2 * x_value)
