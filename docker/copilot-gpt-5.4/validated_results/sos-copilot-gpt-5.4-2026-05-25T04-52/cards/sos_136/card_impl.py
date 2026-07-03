"""Card implementation for Unsubtle Mockery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class UnsubtleMockery(Instant):
    """Unsubtle Mockery."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Unsubtle Mockery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
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
        if not (
            isinstance(target, Creature)
            and any(game.get_battlefield(player).contains(target) for player in game.players)
        ):
            return

        deal_damage(game, self, target, 4)

        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        if len(library) == 0:
            return

        top_card = library.top(1)[0]
        if controller.choose_yes_no("Put the top card of your library into your graveyard?"):
            move_to_zone(game, top_card, Zone.LIBRARY, Zone.GRAVEYARD)
