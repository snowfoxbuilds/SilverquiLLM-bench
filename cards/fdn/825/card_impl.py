"""Card implementation for SublimeEpiphany."""

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

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

def _bounce(game: Any, obj: Any) -> None:
    """Return *obj* from the battlefield to its owner's hand."""
    from engine.types import Zone
    from engine.zones import move_to_zone
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            move_to_zone(game, obj, Zone.BATTLEFIELD, Zone.HAND)
            return


class SublimeEpiphany(Instant):
    """Sublime Epiphany — {4}{U}{U} — Choose one or more.

    - Counter target spell.
    - Counter target activated or triggered ability.
    - Copy target creature you control.
    - Target player draws a card.
    - Return target nonland permanent to its owner's hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sublime Epiphany")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one or more —\n"
            "• Counter target spell.\n"
            "• Counter target activated or triggered ability.\n"
            "• Copy target creature you control.\n"
            "• Target player draws a card.\n"
            "• Return target nonland permanent to its owner's hand.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Counter Spell", description="Counter target spell."),
            Mode(name="Counter Ability", description="Counter target activated or triggered ability."),
            Mode(name="Copy Creature", description="Copy target creature you control."),
            Mode(name="Draw", description="Target player draws a card."),
            Mode(name="Bounce", description="Return target nonland permanent to its owner's hand."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Counter target spell (simplified stub — would need stack access).
                pass
            elif mode == 1:
                # Counter target activated or triggered ability (simplified stub).
                pass
            elif mode == 2:
                # Copy target creature you control (simplified stub).
                pass
            elif mode == 3:
                # Target player draws a card.
                from engine.game import draw_card
                controller = _get_controller(self)
                if controller is not None:
                    draw_card(game, controller)
            elif mode == 4:
                # Return target nonland permanent to its owner's hand.
                target = _get_target(self)
                if target is not None and _is_on_battlefield(game, target):
                    _bounce(game, target)


__all__ = ["SublimeEpiphany"]
