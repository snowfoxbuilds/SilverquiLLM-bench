"""Card implementation for DeadlyPlot."""

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


def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, "controller", None)

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


class DeadlyPlot(Instant):
    """Deadly Plot — {3}{B} — Choose one.

    - Destroy target creature or planeswalker.
    - Return target Zombie creature card from your graveyard to the
      battlefield tapped.

    FDN collector number 520.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Deadly Plot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Destroy target creature or planeswalker.\n"
            "• Return target Zombie creature card from your graveyard to the battlefield tapped.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Destroy", description="Destroy target creature or planeswalker."),
            Mode(name="Reanimate Zombie", description="Return target Zombie creature card from your graveyard to the battlefield tapped."),
        ]

    def on_resolve(self, game: GameState) -> None:
        mode = self.chosen_mode
        if mode is None:
            return
        if mode == 0:
            from engine.game import destroy
            target = _get_target(self)
            if target is not None and _is_on_battlefield(game, target):
                destroy(game, target)
        elif mode == 1:
            # Return target Zombie from graveyard to battlefield tapped.
            target = _get_target(self)
            controller = _get_controller(self)
            if target is not None and controller is not None:
                graveyard = controller.zones[Zone.GRAVEYARD]
                if graveyard.contains(target):
                    from engine.zones import move_to_zone
                    target.controller = controller
                    target.is_tapped = True
                    move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)


__all__ = ["DeadlyPlot"]
