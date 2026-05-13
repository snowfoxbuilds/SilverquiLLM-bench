"""Card implementation for CollectiveBrutality."""

from __future__ import annotations


from engine.card import Instant, Mode, Sorcery
from engine.types import CardType, ManaCost
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


class CollectiveBrutality(Sorcery):
    """Collective Brutality — {1}{B} — Choose one. Escalate — discard a card.

    - Target opponent reveals their hand. You choose a noncreature, nonland card.
      That player discards that card.
    - Target creature gets -2/-2 until end of turn.
    - Target opponent loses 2 life and you gain 2 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Collective Brutality")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Escalate — Discard a card.\n"
            "Choose one or more —\n"
            "• Target opponent reveals their hand. You choose a noncreature, "
            "nonland card from it. That player discards that card.\n"
            "• Target creature gets -2/-2 until end of turn.\n"
            "• Target opponent loses 2 life and you gain 2 life.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Discard", description="Target opponent reveals hand, discards a noncreature, nonland card."),
            Mode(name="Shrink", description="Target creature gets -2/-2 until end of turn."),
            Mode(name="Drain", description="Target opponent loses 2 life and you gain 2 life."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Target opponent discards a noncreature, nonland card (simplified stub).
                pass
            elif mode == 1:
                # Target creature gets -2/-2 until end of turn.
                target = _get_target(self)
                if target is not None and hasattr(target, "base_power"):
                    target.base_power -= 2
                    target.base_toughness -= 2
            elif mode == 2:
                # Target opponent loses 2 life and you gain 2 life.
                from engine.game import deal_damage
                controller = _get_controller(self)
                target = _get_target(self)
                if target is not None and hasattr(target, "life"):
                    target.life -= 2
                if controller is not None:
                    controller.life += 2


__all__ = ["CollectiveBrutality"]
