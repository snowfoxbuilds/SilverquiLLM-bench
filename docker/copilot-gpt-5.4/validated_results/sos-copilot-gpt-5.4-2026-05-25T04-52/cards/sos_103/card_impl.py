"""Card implementation for Ulna Alley Shopkeep."""

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


class UlnaAlleyShopkeep(Creature):
    """Ulna Alley Shopkeep."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ulna Alley Shopkeep")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Goblin", "Warlock"})
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Menace\nInfusion — This creature gets +2/+0 as long as you gained life this turn.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def register_triggers(self, game: GameState) -> None:
        if self._effect_ref is None:
            effects = self.apply_continuous_effect(game)
            self._effect_ref = effects[0] if effects else None

    def apply_continuous_effect(self, game: GameState) -> list[ContinuousEffect]:
        source = self

        def _apply(g: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None or not source.is_on_battlefield(g):
                return
            if getattr(current_controller, "life_gained_this_turn", 0) <= 0:
                return
            source.modified_power += 2

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        existing = game.effect_manager.get_effects_by_source(self)
        if existing:
            return existing
        registered = game.effect_manager.add(effect)
        return [registered]
