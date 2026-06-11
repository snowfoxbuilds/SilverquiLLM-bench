"""Card implementation for Decorum Dissertation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class DecorumDissertation(Sorcery):
    """Decorum Dissertation — {3}{B}{B} — Sorcery — Lesson.

    Target player draws two cards and loses 2 life.
    Paradigm (Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy from exile free at beginning of each
    first main phase.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Decorum Dissertation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault("keywords", Keyword.PARADIGM)
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return
        player = targets[0]
        # Draw two cards
        library = game.get_library(player)
        hand = game.get_hand(player)
        for _ in range(2):
            cards = library.get_all()
            if cards:
                card = cards[-1]
                library.remove(card)
                hand.add(card)
        # Lose 2 life
        player.life -= 2
        # Paradigm: exile this spell after resolution
        controller = self.controller or self.owner
        exile = game.get_exile(controller)
        exile.add(self)
