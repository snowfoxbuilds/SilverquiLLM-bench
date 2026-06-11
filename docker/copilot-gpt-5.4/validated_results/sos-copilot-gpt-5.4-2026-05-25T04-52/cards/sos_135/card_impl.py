"""Card implementation for Tome Blast."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class TomeBlast(Sorcery):
    """Tome Blast."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Tome Blast")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{4}{R}")

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "life")
                    or isinstance(obj, (Creature, Planeswalker))
                ),
                description="target creature, planeswalker, or player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0]
        if target is None:
            return
        deal_damage(game, self, target, 2)
