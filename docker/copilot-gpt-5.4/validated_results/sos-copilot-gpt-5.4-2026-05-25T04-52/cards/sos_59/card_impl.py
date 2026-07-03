"""Card implementation for Matterbending Mage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MatterbendingMage(Creature):
    """Matterbending Mage."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Matterbending Mage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def _etb_target_requirement(self) -> TargetRequirement:
        source = self
        return TargetRequirement(
            filter_fn=lambda obj, _source=source: isinstance(obj, Creature) and obj is not _source,
            description="up to one other target creature",
            zone=Zone.BATTLEFIELD,
        )

    def _resolve_bounce(self, game: GameState, target: object | None) -> None:
        if not isinstance(target, Creature) or not target.is_on_battlefield(game):
            return
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.HAND)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        for player in game.players:
            if player.zones[Zone.STACK].contains(self):
                return []
        return [self._etb_target_requirement()]

    def on_resolve(self, game: GameState) -> None:
        for player in game.players:
            if player.zones[Zone.STACK].contains(self):
                return
        target = getattr(self, "chosen_targets", [None])[0] if getattr(self, "chosen_targets", None) else None
        self._resolve_bounce(game, target)

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        if getattr(source, "_registering_after_enter_battlefield", False):
            def _etb_effect(game: GameState) -> None:
                current_controller = getattr(source, "controller", None)
                if current_controller is None or not source.is_on_battlefield(game):
                    return
                requirement = source._etb_target_requirement()
                candidates = [
                    permanent
                    for player in game.players
                    for permanent in game.get_battlefield(player).get_all()
                    if requirement.filter_fn(permanent)
                ]
                if not candidates:
                    return
                try:
                    target = current_controller.choose_target(candidates, requirement)
                except Exception:
                    target = None
                if target not in candidates:
                    target = None
                source._resolve_bounce(game, target)

            game.stack.push(
                StackObject(
                    source=self,
                    controller=controller,
                    on_resolve=_etb_effect,
                )
            )

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:  # noqa: ARG001
            current_controller = getattr(source, "controller", None)
            spell = getattr(event, "spell", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and spell is not None
                and getattr(getattr(spell, "mana_cost", None), "x_count", 0) > 0
            )

        def _effect(game: GameState) -> None:
            if not source.is_on_battlefield(game):
                return

            def _apply(_game: GameState) -> None:
                source._cant_be_blocked = True

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.ABILITY,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
