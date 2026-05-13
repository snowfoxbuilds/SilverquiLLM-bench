"""Card implementation for AbzanCharm."""

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

def _get_targets(card: Any) -> list[Any]:
    """Return chosen targets list."""
    return getattr(card, "chosen_targets", []) or []

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class AbzanCharm(Instant):
    """Abzan Charm — {W}{B}{G} — Choose one.

    - Exile target creature with power 3 or greater.
    - You draw two cards and you lose 2 life.
    - Distribute two +1/+1 counters among one or two target creatures.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abzan Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Exile target creature with power 3 or greater.\n"
            "• You draw two cards and you lose 2 life.\n"
            "• Distribute two +1/+1 counters among one or two target creatures.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Exile", description="Exile target creature with power 3 or greater."),
            Mode(name="Draw", description="You draw two cards and you lose 2 life."),
            Mode(name="Counters", description="Distribute two +1/+1 counters among one or two target creatures."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen mode."""
        mode = self.chosen_mode
        if mode is None:
            return
        if mode == 0:
            # Exile target creature with power 3 or greater.
            target = _get_target(self)
            if target is not None and _is_on_battlefield(game, target):
                from engine.game import exile
                exile(game, target)
        elif mode == 1:
            # Draw two cards and lose 2 life.
            from engine.game import draw_card
            controller = _get_controller(self)
            if controller is not None:
                draw_card(game, controller)
                draw_card(game, controller)
                controller.life -= 2
        elif mode == 2:
            # Distribute two +1/+1 counters among targets.
            targets = _get_targets(self)
            if targets:
                counters_each = 2 // len(targets)
                remainder = 2 % len(targets)
                for i, t in enumerate(targets):
                    c = counters_each + (1 if i < remainder else 0)
                    if hasattr(t, "plus_one_counters"):
                        t.plus_one_counters += c
                        t._original_plus_one_counters = t.plus_one_counters


__all__ = ["AbzanCharm"]
