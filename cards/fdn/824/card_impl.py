"""Card implementation for PrismariCommand."""

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


class PrismariCommand(Instant):
    """Prismari Command — {1}{U}{R} — Choose two.

    - Prismari Command deals 2 damage to any target.
    - Target player creates a Treasure token.
    - Target player draws two cards, then discards two cards.
    - Destroy target artifact.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Prismari Command")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two —\n"
            "• Prismari Command deals 2 damage to any target.\n"
            "• Target player creates a Treasure token.\n"
            "• Target player draws two cards, then discards two cards.\n"
            "• Destroy target artifact.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Damage", description="Deal 2 damage to any target."),
            Mode(name="Treasure", description="Target player creates a Treasure token."),
            Mode(name="Loot", description="Target player draws two cards, then discards two cards."),
            Mode(name="Destroy Artifact", description="Destroy target artifact."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Deal 2 damage to any target.
                from engine.game import deal_damage
                target = _get_target(self)
                if target is not None:
                    deal_damage(game, self, target, 2)
            elif mode == 1:
                # Target player creates a Treasure token.
                from engine.card import Artifact
                from engine.game import create_token
                controller = _get_controller(self)
                if controller is not None:
                    token = Artifact(name="Treasure")
                    create_token(game, controller, token)
            elif mode == 2:
                # Target player draws two cards, then discards two cards.
                from engine.game import draw_card, discard
                controller = _get_controller(self)
                if controller is not None:
                    draw_card(game, controller)
                    draw_card(game, controller)
                    # Discard 2 (simplified: discard from hand if available)
                    hand = game.get_hand(controller)
                    for _ in range(2):
                        cards = hand.get_all()
                        if cards:
                            discard(game, controller, cards[0])
            elif mode == 3:
                # Destroy target artifact.
                from engine.game import destroy
                target = _get_target(self)
                if target is not None and _is_on_battlefield(game, target):
                    destroy(game, target)


__all__ = ["PrismariCommand"]
