"""Card implementation for Comforting Counsel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Enchantment
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
from benchmarks.sos.workspace.engine.game import add_counter
from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
from benchmarks.sos.workspace.engine.types import ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ComfortingCounsel(Enchantment):
    """Comforting Counsel."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Comforting Counsel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)
        self._continuous_effect_ref: ContinuousEffect | None = None

    def register_triggers(self, game: GameState) -> None:
        self.apply_continuous_effect(game)
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(g: GameState, event: GainsLifeTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            return (
                current_controller is not None
                and event.player is current_controller
                and source.is_on_battlefield(g)
            )

        def _effect(g: GameState) -> None:
            if source.is_on_battlefield(g):
                add_counter(g, source, "growth")
                g.effect_manager.apply_all(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=GainsLifeTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def apply_continuous_effect(self, game: GameState) -> list[ContinuousEffect]:
        source = self

        def _apply(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(g):
                return
            if source.counters.get("growth", 0) < 5:
                return
            for permanent in g.get_battlefield(current_controller).get_all():
                if isinstance(permanent, Creature):
                    permanent.modified_power += 3
                    permanent.modified_toughness += 3

        existing = game.effect_manager.get_effects_by_source(self)
        if existing:
            return existing
        effect = game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_PERMANENT,
            )
        )
        self._continuous_effect_ref = effect
        return [effect]
