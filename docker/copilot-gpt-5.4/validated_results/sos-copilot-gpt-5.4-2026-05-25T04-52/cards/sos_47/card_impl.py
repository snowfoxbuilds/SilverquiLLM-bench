"""Card implementation for Essence Scatter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class EssenceScatter(Instant):
    """Essence Scatter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Essence Scatter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    isinstance(obj, StackObject)
                    and bool(getattr(obj, "is_spell", False))
                    and CardType.CREATURE in getattr(getattr(obj, "source", None), "card_types", set())
                ),
                description="target creature spell",
                zone=Zone.STACK,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if not isinstance(target, StackObject) or not getattr(target, "is_spell", False):
            return
        if not game.stack.contains(target):
            return
        game.stack.remove(target)
        target_spell = getattr(target, "source", None)
        if target_spell is not None:
            move_to_zone(game, target_spell, Zone.STACK, Zone.GRAVEYARD)
