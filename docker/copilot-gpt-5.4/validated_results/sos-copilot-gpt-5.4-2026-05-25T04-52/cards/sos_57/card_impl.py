"""Card implementation for Mana Sculpt."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant
from benchmarks.sos.workspace.engine.events import BeginningOfMainPhaseTriggeredEvent
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ManaSculpt(Instant):
    """Mana Sculpt."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mana Sculpt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, StackObject) and bool(getattr(obj, "is_spell", False)),
                description="target spell",
                zone=Zone.STACK,
            )
        ]

    def _controller_has_wizard(self, game: GameState) -> bool:
        controller = self.controller
        if controller is None:
            return False
        return any(
            "Wizard" in getattr(permanent, "subtypes", set())
            for permanent in game.get_battlefield(controller).get_all()
        )

    def _register_delayed_mana(self, game: GameState, amount: int) -> None:
        controller = self.controller
        if controller is None or amount <= 0:
            return
        delayed_source = object()

        def _condition(game: GameState, event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return event.player is controller

        def _effect(game: GameState) -> None:
            controller.mana_pool.add(ManaType.COLORLESS, amount)
            game.trigger_manager.unregister(delayed_source)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=delayed_source,
                controller=controller,
            )
        )

    def on_resolve(self, game: GameState) -> None:
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        if not isinstance(target, StackObject) or not getattr(target, "is_spell", False):
            return
        if not game.stack.contains(target):
            return
        game.stack.remove(target)
        target_spell = getattr(target, "source", None)
        mana_spent = int(getattr(target_spell, "mana_spent", 0))
        if target_spell is not None:
            destination = Zone.EXILE if getattr(target, "exile_on_resolve", False) else Zone.GRAVEYARD
            move_to_zone(game, target_spell, Zone.STACK, destination)
        if self._controller_has_wizard(game):
            self._register_delayed_mana(game, mana_spent)
