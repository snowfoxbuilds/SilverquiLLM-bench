"""Card implementation for Lorehold, the Historian."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class LoreholdTheHistorian(Creature):
    """Lorehold, the Historian — {3}{R}{W} — 5/5 — Legendary Elder Dragon.

    Flying, haste
    Each instant and sorcery card in your hand has miracle {2}.
    At the beginning of each opponent's upkeep, you may discard a card.
    If you do, draw a card.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lorehold, the Historian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}{W}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the miracle-granting static ability."""
        self._apply_miracle_to_hand(game)

    def _apply_miracle_to_hand(self, game: "GameState") -> None:
        """Grant miracle {2} to instants/sorceries in controller's hand."""
        if self.controller is None:
            return
        hand = game.get_hand(self.controller)
        for card in hand.get_all():
            if CardType.INSTANT in getattr(card, 'card_types', set()) or \
               CardType.SORCERY in getattr(card, 'card_types', set()):
                card.miracle_cost = ManaCost.parse("{2}")

    def get_miracle_cost(self, card: Any) -> "ManaCost | None":
        """Return miracle cost for an instant/sorcery, None otherwise."""
        card_types = getattr(card, 'card_types', set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return ManaCost.parse("{2}")
        return None

    def get_upkeep_triggers(self, game: "GameState", active_player: Any) -> list[Any]:
        """Return triggers for upkeep. Only triggers on opponent's upkeep."""
        if active_player is self.controller:
            return []
        return [self._upkeep_trigger]

    def _upkeep_trigger(self, game: "GameState") -> None:
        """Discard a card, then draw a card."""
        self.on_upkeep_trigger(game, None)

    def on_upkeep_trigger(self, game: "GameState", active_player: Any) -> None:
        """Execute the upkeep trigger: discard 1, draw 1."""
        if self.controller is None:
            return
        hand = game.get_hand(self.controller)
        cards_in_hand = hand.get_all()
        if not cards_in_hand:
            return
        # Discard first card (deterministic)
        to_discard = cards_in_hand[0]
        hand.remove(to_discard)
        game.get_graveyard(self.controller).add(to_discard)
        # Draw a card
        library = game.get_library(self.controller)
        lib_cards = library.get_all()
        if lib_cards:
            drawn = lib_cards[-1]  # draw from top
            library.remove(drawn)
            hand.add(drawn)
