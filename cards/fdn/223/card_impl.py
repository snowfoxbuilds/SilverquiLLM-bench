"""Card implementation for Giant Growth."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ContinuousEffect, Instant
from engine.continuous_effects import Layer, SubLayer
from engine.types import (
    CardType,
    ManaCost,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState




def _get_chosen_target(card: Any, game: Any) -> Any:
    """Retrieve the first chosen target for a spell.

    Looks for ``chosen_targets`` (set by :func:`cast_spell` during the
    real casting pipeline) first, then falls back to the test-backdoor
    attribute ``_resolve_target``.
    """
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)
class GiantGrowth(Instant):
    """Giant Growth — {G} — Target creature gets +3/+3 until end of turn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Giant Growth")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault(
            "rules_text", "Target creature gets +3/+3 until end of turn."
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        """Target creature on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        """Apply +3/+3 until end of turn as a continuous effect in layer 7c."""
        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify target is still a legal creature on the battlefield.
        still_valid = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    still_valid = True
                    break
        if not still_valid:
            return

        # Create a continuous effect that gives +3/+3 in layer 7c.
        creature_ref = target

        def _apply_buff(game: GameState) -> None:
            # Only apply if the creature is still on the battlefield.
            for p in game.players:
                if game.get_battlefield(p).contains(creature_ref):
                    creature_ref.base_power += 3
                    creature_ref.base_toughness += 3
                    return

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_buff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)
