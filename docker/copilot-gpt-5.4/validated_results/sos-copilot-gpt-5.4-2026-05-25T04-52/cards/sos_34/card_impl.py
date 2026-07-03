"""Card implementation for Stand Up for Yourself."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


def _get_target(card: Any) -> Any:
    chosen_targets = getattr(card, "chosen_targets", None)
    if chosen_targets:
        return chosen_targets[0]
    return None


class StandUpForYourself(Instant):
    """Stand Up for Yourself."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Stand Up for Yourself")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("rules_text", "Destroy target creature with power 3 or greater.")
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature) and obj.power >= 3,
                description="target creature with power 3 or greater",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = _get_target(self)
        if not isinstance(target, Creature) or target.power < 3:
            return
        if not any(game.get_battlefield(player).contains(target) for player in game.players):
            return
        destroy(game, target)
