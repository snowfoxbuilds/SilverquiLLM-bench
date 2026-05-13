"""Card implementation for ValorousStance."""

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

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class ValorousStance(Instant):
    """Valorous Stance — {1}{W} — Choose one.

    - Target creature gains indestructible until end of turn.
    - Destroy target creature with toughness 4 or greater.

    FDN collector number 583.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Valorous Stance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Target creature gains indestructible until end of turn.\n"
            "• Destroy target creature with toughness 4 or greater.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Indestructible", description="Target creature gains indestructible until end of turn."),
            Mode(name="Destroy", description="Destroy target creature with toughness 4 or greater."),
        ]

    def on_resolve(self, game: GameState) -> None:
        mode = self.chosen_mode
        if mode is None:
            return
        if mode == 0:
            target = _get_target(self)
            if target is not None and hasattr(target, "keywords"):
                target.keywords = target.keywords | Keyword.INDESTRUCTIBLE
        elif mode == 1:
            from engine.game import destroy
            target = _get_target(self)
            if target is not None and _is_on_battlefield(game, target):
                toughness = getattr(target, "toughness", 0)
                if toughness >= 4:
                    destroy(game, target)


__all__ = ["ValorousStance"]
