"""Card implementation for Arcane Omens."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ArcaneOmens(Sorcery):
    """Arcane Omens — {4}{B} — Sorcery.

    Converge — Target player discards X cards, where X is the number of
    colors of mana spent to cast this spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arcane Omens")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{B}"))
        super().__init__(**kwargs)
        self.colors_of_mana_spent: int = 0

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", None)
        if not targets:
            return
        target_player = targets[0]

        x = self.colors_of_mana_spent
        if x <= 0:
            return

        hand = game.get_hand(target_player)
        graveyard = game.get_graveyard(target_player)

        cards_in_hand = hand.get_all()
        discard_count = min(x, len(cards_in_hand))

        # Discard from the beginning of hand
        for card in cards_in_hand[:discard_count]:
            hand.remove(card)
            graveyard.add(card)
