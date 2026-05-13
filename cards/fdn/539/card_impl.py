"""Card implementation for GoblinOriflamme."""

from __future__ import annotations


from engine.card import Artifact, Aura, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class GoblinOriflamme(Enchantment):
    """Goblin Oriflamme — {1}{R} — Attacking creatures you control get +1/+0.

    Implements a layer 7c continuous effect that gives +1/+0 to all
    attacking creatures the controller controls.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Oriflamme")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Attacking creatures you control get +1/+0.",
        )
        super().__init__(**kwargs)
        self._effect_ref: ContinuousEffect | None = None

    def on_resolve(self, game: GameState) -> None:
        """Register the continuous effect when entering the battlefield."""
        self._register_effect(game)

    def _register_effect(self, game: GameState) -> None:
        """Register the +1/+0 to attacking creatures continuous effect."""
        enchantment_ref = self

        def _apply_oriflamme(game: GameState) -> None:
            controller = enchantment_ref.controller
            if controller is None:
                return
            # Check the enchantment is still on the battlefield
            if not _is_on_battlefield(game, enchantment_ref):
                return
            for obj in game.get_battlefield(controller).get_all():
                if (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                    and getattr(obj, "is_attacking", False)
                ):
                    obj.base_power += 1

        effect = ContinuousEffect(
            source=enchantment_ref,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_oriflamme,
            duration=DURATION_PERMANENT,
        )
        self._effect_ref = game.effect_manager.add(effect)

    def register_replacement_effects(self, game: GameState) -> None:
        """Register the continuous effect when entering via casting pipeline."""
        if self._effect_ref is None:
            self._register_effect(game)


__all__ = ["GoblinOriflamme"]
