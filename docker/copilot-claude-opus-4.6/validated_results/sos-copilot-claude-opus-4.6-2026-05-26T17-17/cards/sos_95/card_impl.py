"""Card implementation for Pull from the Grave."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PullFromTheGrave(Sorcery):
    """Pull from the Grave — {2}{B} — Sorcery.

    Return up to two target creature cards from your graveyard to your hand.
    You gain 2 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pull from the Grave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Return up to two target creature cards from your graveyard to "
            "your hand. You gain 2 life.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Return up to two creature cards from graveyard to hand, gain 2 life."""
        controller = self.controller
        targets = getattr(self, "chosen_targets", None) or getattr(self, "_explicit_targets", [])

        graveyard = game.get_graveyard(controller)
        hand = game.get_hand(controller)

        for target in targets:
            if graveyard.contains(target):
                graveyard.remove(target)
                hand.add(target)

        # Gain 2 life
        controller.life += 2
        if hasattr(controller, "life_gained_this_turn"):
            controller.life_gained_this_turn += 2
        else:
            controller.life_gained_this_turn = 2
