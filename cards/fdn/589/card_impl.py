"""Card implementation for FinaleOfRevelation."""

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


class FinaleOfRevelation(Sorcery):
    """Finale of Revelation — {X}{U}{U}

    Draw X cards. If X is 10 or more, instead shuffle your graveyard
    into your library, draw X cards, untap up to five lands, and you
    have no maximum hand size for the rest of the game.
    Exile Finale of Revelation.

    FDN collector number 589.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Finale of Revelation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Draw X cards. If X is 10 or more, instead shuffle your graveyard "
            "into your library, draw X cards, untap up to five lands, and you "
            "have no maximum hand size for the rest of the game.\n"
            "Exile Finale of Revelation.",
        )
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: GameState) -> None:
        from engine.game import draw_card
        controller = _get_controller(self)
        if controller is None:
            return
        x = self.x_value
        if x >= 10:
            # Shuffle graveyard into library
            gy = controller.zones[Zone.GRAVEYARD]
            lib = controller.zones[Zone.LIBRARY]
            for card in list(gy.get_all()):
                gy.remove(card)
                lib.add(card)
            lib.shuffle()
        # Draw X cards
        for _ in range(x):
            draw_card(game, controller)


__all__ = ["FinaleOfRevelation"]
