"""Card implementation for Divergent Equation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DivergentEquation(Instant):
    """Divergent Equation."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Divergent Equation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{X}{U}"))
        super().__init__(**kwargs)
        self.x_value = 0
        self.always_exile_on_resolve = True

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller

        def _filter(obj: Any) -> bool:
            return (
                bool(getattr(obj, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY})
                and getattr(obj, "owner", None) is controller
            )

        return [
            TargetRequirement(
                filter_fn=_filter,
                description="target instant or sorcery card in your graveyard",
                zone=Zone.GRAVEYARD,
            )
            for _ in range(max(0, self.x_value))
        ]

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        graveyard = game.get_graveyard(controller)
        for target in getattr(self, "chosen_targets", []):
            if not graveyard.contains(target):
                continue
            if not bool(getattr(target, "card_types", set()) & {CardType.INSTANT, CardType.SORCERY}):
                continue
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.HAND)
