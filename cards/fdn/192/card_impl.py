"""Card implementation for BurstLightning."""

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


class BurstLightning(Instant):
    """Burst Lightning — {R}

    Kicker {4}.
    Burst Lightning deals 2 damage to any target. If this spell was
    kicked, it deals 4 damage instead.

    FDN collector number 192.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Burst Lightning")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {4}\n"
            "Burst Lightning deals 2 damage to any target. If this spell was kicked, it deals 4 damage instead.",
        )
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse("{4}")

    def on_resolve(self, game: GameState) -> None:
        from engine.game import deal_damage
        target = _get_target(self)
        if target is not None:
            damage = 4 if self.kicked else 2
            deal_damage(game, self, target, damage)


__all__ = ["BurstLightning"]
