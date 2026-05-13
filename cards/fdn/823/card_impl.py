"""Card implementation for BorosCharm."""

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


class BorosCharm(Instant):
    """Boros Charm — {R}{W} — Choose one.

    - Boros Charm deals 4 damage to target player or planeswalker.
    - Permanents you control gain indestructible until end of turn.
    - Target creature gains double strike until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Boros Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Boros Charm deals 4 damage to target player or planeswalker.\n"
            "• Permanents you control gain indestructible until end of turn.\n"
            "• Target creature gains double strike until end of turn.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Damage", description="Deal 4 damage to target player or planeswalker."),
            Mode(name="Indestructible", description="Permanents you control gain indestructible until end of turn."),
            Mode(name="Double Strike", description="Target creature gains double strike until end of turn."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen mode."""
        mode = self.chosen_mode
        if mode is None:
            return
        if mode == 0:
            # Deal 4 damage to target player or planeswalker.
            from engine.game import deal_damage
            target = _get_target(self)
            if target is not None:
                deal_damage(game, self, target, 4)
        elif mode == 1:
            # Permanents you control gain indestructible until end of turn.
            from engine.types import Keyword
            controller = _get_controller(self)
            if controller is not None:
                for obj in game.get_battlefield(controller).get_all():
                    obj.keywords = obj.keywords | Keyword.INDESTRUCTIBLE
        elif mode == 2:
            # Target creature gains double strike until end of turn.
            from engine.types import Keyword
            target = _get_target(self)
            if target is not None and hasattr(target, "keywords"):
                target.keywords = target.keywords | Keyword.DOUBLE_STRIKE


__all__ = ["BorosCharm"]
