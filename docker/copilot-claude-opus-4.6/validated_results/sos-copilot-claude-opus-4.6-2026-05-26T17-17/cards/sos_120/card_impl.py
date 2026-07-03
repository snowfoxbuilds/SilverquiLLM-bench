"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.
    Paradigm (Then exile this spell.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        super().__init__(**kwargs)
        # Add PARADIGM keyword
        from engine.types import _KeywordSentinel
        self.keywords = Keyword.PARADIGM  # type: ignore[assignment]

    def on_resolve(self, game: "GameState") -> None:
        """Resolve: exile from library until MV >= 4, then paradigm self-exile."""
        controller = self.controller or self.owner
        library = game.get_library(controller)
        exile = game.get_exile(controller)

        total_mv = 0
        exiled_cards: list[Any] = []

        # Exile cards from top until total MV >= 4
        while total_mv < 4 and len(library) > 0:
            # Top of library is last element in internal list
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[0]
            library.remove(card)
            mc = getattr(card, "mana_cost", None)
            if mc is not None:
                mv = mc.cmc if hasattr(mc, "cmc") else 0
            else:
                mv = 0
            total_mv += mv
            exiled_cards.append(card)
            exile.add(card)

        # Paradigm: exile this spell itself
        exile.add(self)

