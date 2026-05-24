"""Card implementation for Anthem of Champions."""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ActivatedAbility, Creature, Enchantment
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from benchmarks.sos.workspace.cards.registry import CardRegistry

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class AnthemOfChampions(Enchantment):
    """Anthem of Champions — {G}{W} — Creatures you control get +1/+1.

    FDN collector number 116.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Anthem of Champions")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Creatures you control get +1/+1.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        enchantment_ref = self

        def _apply(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    obj.modified_power += 1
                    obj.modified_toughness += 1

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        if self._effect_ref is None:
            self._register_effect(game)
