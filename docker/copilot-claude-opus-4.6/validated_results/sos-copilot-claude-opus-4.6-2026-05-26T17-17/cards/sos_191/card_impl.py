"""Card implementation for Geometer's Arthropod."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class _XSpellTrigger:
    """Triggered ability: cast spell with {X} -> look at top X, put 1 in hand."""

    def __init__(self, source: "GeometersArthropod") -> None:
        self.source = source
        self.description = "Whenever you cast a spell with {X} in its mana cost, look at the top X cards of your library. Put one of them into your hand and the rest on the bottom of your library in a random order."

    def resolve(self, game: "GameState", x: int = 0) -> None:
        """Resolve: look at top X, put 1 in hand, rest on bottom."""
        if x <= 0:
            return
        controller = self.source.controller
        if controller is None:
            return
        library = controller.library if hasattr(controller, "library") else []
        top_cards = library[:x] if len(library) >= x else library[:]
        if not top_cards:
            return
        # Put the first one in hand, rest on bottom (simplified)
        chosen = top_cards[0]
        for card in top_cards:
            if card in library:
                library.remove(card)
        from engine.types import Zone
        controller.zones[Zone.HAND].add(chosen)
        chosen.zone = Zone.HAND
        import random
        rest = [c for c in top_cards if c is not chosen]
        random.shuffle(rest)
        library[0:0] = rest  # put on bottom (index 0 is bottom)


class GeometersArthropod(Creature):
    """Geometer's Arthropod — {G}{U} — Creature — Fractal Crab — 1/4.

    Whenever you cast a spell with {X} in its mana cost, look at the top X
    cards of your library. Put one of them into your hand and the rest on the
    bottom of your library in a random order.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Geometer's Arthropod")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{U}"))
        kwargs.setdefault("subtypes", {"Fractal", "Crab"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def get_triggered_abilities(self, game: "GameState") -> list[Any]:
        """Return the X-spell trigger."""
        return [_XSpellTrigger(self)]

    def check_trigger(self, game: "GameState", event: Any) -> bool:
        """Check if a spell cast event has {X} in its mana cost."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return False
        mana_cost = getattr(spell, "mana_cost", None)
        if mana_cost is None:
            return False
        return getattr(mana_cost, "x_count", 0) > 0
