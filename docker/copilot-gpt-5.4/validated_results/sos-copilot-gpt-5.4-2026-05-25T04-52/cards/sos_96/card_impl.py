"""Card implementation for Rabid Attack."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import CreatureDiesTriggeredEvent
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class RabidAttack(Instant):
    """Rabid Attack."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rabid Attack")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            'Until end of turn, any number of target creatures you control each get +1/+0 and gain '
            '"When this creature dies, draw a card."',
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        controller = self.controller
        requirement = TargetRequirement(
            filter_fn=lambda obj: isinstance(obj, Creature) and getattr(obj, "controller", None) is controller,
            description="any number of target creatures you control",
            zone=Zone.BATTLEFIELD,
        )
        requirement.min_targets = 0  # type: ignore[attr-defined]
        requirement.max_targets = 99  # type: ignore[attr-defined]
        requirement.distinct_targets = True  # type: ignore[attr-defined]
        return [requirement]

    def _grant_draw_when_dies(self, game: GameState, creature: Creature) -> None:
        controller = self.controller
        if controller is None:
            return
        expires_turn = game.turn_number
        delayed_source = object()

        def _condition(_game: GameState, event: CreatureDiesTriggeredEvent) -> bool:
            return _game.turn_number == expires_turn and event.creature is creature

        def _cleanup(g: GameState) -> None:
            g.trigger_manager.unregister(delayed_source)

        def _effect(g: GameState) -> None:
            draw_card(g, controller)
            _cleanup(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=CreatureDiesTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=delayed_source,
                controller=controller,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=delayed_source,
                layer=Layer.TEXT,
                apply=lambda _game: None,
                duration=DURATION_END_OF_TURN,
                on_expire=_cleanup,
            )
        )

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        for creature in getattr(self, "chosen_targets", []):
            if (
                not isinstance(creature, Creature)
                or not creature.is_on_battlefield(game)
                or creature.controller is not controller
            ):
                continue

            def _apply(_game: GameState, *, target: Creature = creature) -> None:
                target.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
                    duration=DURATION_END_OF_TURN,
                )
            )
            self._grant_draw_when_dies(game, creature)
        game.effect_manager.apply_all(game)
