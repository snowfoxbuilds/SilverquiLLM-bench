"""Card implementation for Killian's Confidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import DealsDamageTriggeredEvent
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class KilliansConfidence(Sorcery):
    """Killian's Confidence."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Killian's Confidence")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}"))
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
        controller = self.controller
        if controller is None:
            return

        target = self.chosen_targets[0] if getattr(self, "chosen_targets", []) else None
        if isinstance(target, Creature) and target.is_on_battlefield(game):
            def _pump_target(_game: GameState, *, creature: Creature = target) -> None:
                if creature.is_on_battlefield(_game):
                    creature.modified_power += 1
                    creature.modified_toughness += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_pump_target,
                    duration=DURATION_END_OF_TURN,
                )
            )
            game.effect_manager.apply_all(game)

        draw_card(game, controller)

    def on_cast(self, game: GameState) -> None:
        self.register_triggers(game)

    def register_triggers(self, game: GameState) -> None:
        game.trigger_manager.unregister(self)
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: DealsDamageTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            dealing_creature = getattr(event, "source", None)
            damaged_player = getattr(event, "target", None)
            return (
                current_controller is not None
                and source in g.get_graveyard(current_controller).get_all()
                and bool(getattr(event, "is_combat", False) or getattr(event, "combat", False))
                and isinstance(dealing_creature, Creature)
                and getattr(dealing_creature, "controller", None) is current_controller
                and hasattr(damaged_player, "life")
            )

        def _effect(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            if source not in g.get_graveyard(current_controller).get_all():
                return
            if not current_controller.choose_yes_no("Pay {W/B} to return Killian's Confidence?"):
                return
            hybrid_cost = ManaCost.parse("{W/B}")
            if not current_controller.mana_pool.can_pay(hybrid_cost):
                return
            if not current_controller.mana_pool.pay(hybrid_cost):
                return
            move_to_zone(g, source, Zone.GRAVEYARD, Zone.HAND)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=DealsDamageTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
