"""Card implementation for Brush Off."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player


class BrushOff(Instant):
    """Brush Off."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brush Off")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "This spell costs {1}{U} less to cast if it targets an instant or sorcery spell.\n"
            "Counter target spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, StackObject) and bool(getattr(obj, "is_spell", False)),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def get_cast_cost(
        self,
        game: GameState,  # noqa: ARG002
        player: Player,  # noqa: ARG002
        from_zone: Zone,  # noqa: ARG002
        mana_cost: ManaCost,
    ) -> ManaCost:
        target = getattr(self, "_casting_targets", [None])[0] if getattr(self, "_casting_targets", None) else None
        if not isinstance(target, StackObject) or not getattr(target, "is_spell", False):
            return mana_cost
        target_types = getattr(getattr(target, "source", None), "card_types", set())
        if CardType.INSTANT in target_types or CardType.SORCERY in target_types:
            return ManaCost.parse("{1}{U}")
        return mana_cost

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if not isinstance(target, StackObject) or not getattr(target, "is_spell", False):
            return
        if not game.stack.contains(target):
            return
        game.stack.remove(target)
        source_spell = getattr(target, "source", None)
        if source_spell is not None:
            move_to_zone(game, source_spell, Zone.STACK, Zone.GRAVEYARD)
