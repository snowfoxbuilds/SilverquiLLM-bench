"""Card implementation for Germination Practicum."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class GerminationPracticum(Sorcery):
    """Germination Practicum — {3}{G}{G} — Sorcery — Lesson.

    Put two +1/+1 counters on each creature you control.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Germination Practicum")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)
        self._paradigm_exile = True

    def on_resolve(self, game: "GameState") -> None:
        """Put two +1/+1 counters on each creature you control, then exile (paradigm)."""
        controller = self.controller
        if controller is None:
            return

        # Put two +1/+1 counters on each creature controller controls
        bf = game.get_battlefield(controller)
        for card in bf:
            card_types = getattr(card, "card_types", set())
            if CardType.CREATURE in card_types:
                card.plus_one_counters = getattr(card, "plus_one_counters", 0) + 2

        # Paradigm: exile this spell
        exile = game.get_exile(controller)
        exile.add(self)

        # Register paradigm for future main phases
        controller._paradigm_names = getattr(controller, "_paradigm_names", set())
        controller._paradigm_names.add(self.name)
