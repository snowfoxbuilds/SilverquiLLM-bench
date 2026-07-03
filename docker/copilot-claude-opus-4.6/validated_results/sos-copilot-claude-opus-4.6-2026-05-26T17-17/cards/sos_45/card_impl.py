"""Card implementation for Emeritus of Ideation // Ancestral Recall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfIdeationAncestralRecall(Creature):
    """Emeritus of Ideation // Ancestral Recall — {3}{U}{U} — Creature (5/5).

    Flying, ward {2}.
    Enters prepared.
    Whenever this creature attacks, may exile 8 cards from graveyard to become prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Ideation // Ancestral Recall")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.WARD)
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """This creature enters prepared."""
        self.is_prepared = True

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger."""
        pass  # Attack trigger handled via on_attack

    def on_attack(self, game: "GameState", exile_graveyard: bool = False) -> None:
        """Whenever this attacks, may exile 8 cards from graveyard to become prepared."""
        if not exile_graveyard:
            return

        controller = self.controller
        gy = game.get_graveyard(controller)
        gy_cards = list(gy.get_all())

        if len(gy_cards) < 8:
            return

        # Exile 8 cards from graveyard
        for card in gy_cards[:8]:
            gy.remove(card)
            game.get_exile(controller).add(card)

        self.is_prepared = True
