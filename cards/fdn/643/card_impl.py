"""Card implementation for PrimalMight."""

from __future__ import annotations


from engine.card import Creature, Instant, Mode, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _get_target(card: Any) -> Any:
    """Return the first chosen target or the _resolve_target fallback."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

def _get_targets(card: Any) -> list[Any]:
    """Return chosen targets list."""
    return getattr(card, "chosen_targets", []) or []


class PrimalMight(Sorcery):
    """Primal Might — {X}{G}

    Target creature you control gets +X/+X until end of turn. Then it
    fights up to one target creature you don't control.

    FDN collector number 643.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Primal Might")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Target creature you control gets +X/+X until end of turn. "
            "Then it fights up to one target creature you don't control.",
        )
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: GameState) -> None:
        targets = _get_targets(self)
        if not targets:
            return
        x = self.x_value
        my_creature = targets[0]
        # Pump +X/+X
        if hasattr(my_creature, "base_power"):
            my_creature.base_power += x
            my_creature.base_toughness += x
        # Fight if there's a second target
        if len(targets) >= 2:
            from engine.game import deal_damage
            opponent_creature = targets[1]
            deal_damage(game, my_creature, opponent_creature, getattr(my_creature, "power", 0))
            deal_damage(game, opponent_creature, my_creature, getattr(opponent_creature, "power", 0))


__all__ = ["PrimalMight"]
