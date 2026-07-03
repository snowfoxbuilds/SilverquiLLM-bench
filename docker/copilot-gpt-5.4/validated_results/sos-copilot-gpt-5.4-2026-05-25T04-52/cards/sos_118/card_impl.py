"""Card implementation for Heated Argument."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import deal_damage
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class HeatedArgument(Instant):
    """Heated Argument."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heated Argument")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
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
        target_controller = getattr(target, "controller", None)
        if target_controller is None or not game.get_battlefield(target_controller).contains(target):
            return

        deal_damage(game, self, target, 6)

        controller = self.controller
        if controller is None:
            return
        graveyard = game.get_graveyard(controller)
        cards = graveyard.get_all()
        if not cards:
            return

        try:
            should_exile = controller.choose_yes_no("Exile a card from your graveyard?")
        except Exception:
            should_exile = False
        if not should_exile:
            return

        try:
            chosen = controller.choose_card(cards, "Choose a card to exile")
        except Exception:
            chosen = cards[0]
        if chosen is None or not graveyard.contains(chosen):
            return

        move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.EXILE)
        if target_controller is not None:
            deal_damage(game, self, target_controller, 2)
