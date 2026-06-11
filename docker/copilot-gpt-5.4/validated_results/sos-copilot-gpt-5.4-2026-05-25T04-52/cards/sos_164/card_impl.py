"""Card implementation for Thornfist Striker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ThornfistStriker(Creature):
    """Thornfist Striker."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Thornfist Striker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.ward_cost = ManaCost.parse("{1}")

    def register_triggers(self, game: GameState) -> None:
        self.apply_continuous_effect(game)

    def apply_continuous_effect(self, game: GameState) -> list[ContinuousEffect]:
        existing = game.effect_manager.get_effects_by_source(self)
        if existing:
            return existing

        source = self

        def _apply_power(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if (
                current_controller is None
                or not source.is_on_battlefield(g)
                or getattr(current_controller, "life_gained_this_turn", 0) <= 0
            ):
                return
            for creature in g.get_battlefield(current_controller).get_all():
                if isinstance(creature, Creature):
                    creature.modified_power += 1

        def _apply_trample(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if (
                current_controller is None
                or not source.is_on_battlefield(g)
                or getattr(current_controller, "life_gained_this_turn", 0) <= 0
            ):
                return
            for creature in g.get_battlefield(current_controller).get_all():
                if isinstance(creature, Creature):
                    creature.keywords |= Keyword.TRAMPLE

        power_effect = game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_power,
                duration=DURATION_PERMANENT,
            )
        )
        keyword_effect = game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.ABILITY,
                apply=_apply_trample,
                duration=DURATION_PERMANENT,
            )
        )
        return [power_effect, keyword_effect]
