"""Card implementation for InscriptionOfInsight."""

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

def _bounce(game: Any, obj: Any) -> None:
    """Return *obj* from the battlefield to its owner's hand."""
    from engine.types import Zone
    from engine.zones import move_to_zone
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            move_to_zone(game, obj, Zone.BATTLEFIELD, Zone.HAND)
            return


class InscriptionOfInsight(Sorcery):
    """Inscription of Insight — {3}{U} — Kicker {2}{U}{U}. Choose one (all if kicked).

    - Return up to two target creatures to their owners' hands.
    - Scry 2, then draw two cards.
    - Create an X/X blue Illusion creature token, where X is the number of cards in your hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inscription of Insight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {2}{U}{U}\nChoose one. If this spell was kicked, choose any number instead.\n"
            "• Return up to two target creatures to their owners' hands.\n"
            "• Scry 2, then draw two cards.\n"
            "• Create an X/X blue Illusion creature token, where X is the number of "
            "cards in your hand.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Bounce", description="Return up to two target creatures to their owners' hands."),
            Mode(name="Draw", description="Scry 2, then draw two cards."),
            Mode(name="Token", description="Create an X/X blue Illusion creature token."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Return up to two target creatures to their owners' hands.
                targets = _get_targets(self)
                for t in targets[:2]:
                    if _is_on_battlefield(game, t):
                        _bounce(game, t)
            elif mode == 1:
                # Scry 2, then draw two cards.
                from engine.game import draw_card
                controller = _get_controller(self)
                if controller is not None:
                    # Simplified: skip scry, just draw 2.
                    draw_card(game, controller)
                    draw_card(game, controller)
            elif mode == 2:
                # Create an X/X blue Illusion creature token.
                from engine.card import Creature
                from engine.game import create_token
                controller = _get_controller(self)
                if controller is not None:
                    hand = game.get_hand(controller)
                    x = len(hand.get_all())
                    token = Creature(name="Illusion", base_power=x, base_toughness=x)
                    create_token(game, controller, token)


__all__ = ["InscriptionOfInsight"]
