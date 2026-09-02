"""Card implementation for Micromancer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.card_queries import choose_object, query_yes_no
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class Micromancer(Creature):
    """Micromancer — {3}{U} — 3/3 — Human Wizard.

    When this creature enters, you may search your library for an instant
    or sorcery card with mana value 1, reveal it, put it into your hand,
    then shuffle.

    FDN collector number 158.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Micromancer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Human", "Wizard"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may search your library for an "
            "instant or sorcery card with mana value 1, reveal it, put it "
            "into your hand, then shuffle.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: search library for instant/sorcery with MV 1."""
        controller = self.controller
        if controller is None:
            return
        # Optional — ask if they want to search
        if not query_yes_no(game, controller, "Search your library for an instant or sorcery with mana value 1?", source_card=self):
            return
        library = controller.zones[Zone.LIBRARY]
        candidates = []
        for card in library.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                mana_cost = getattr(card, "mana_cost", None)
                if mana_cost is not None and mana_cost.cmc == 1:
                    candidates.append(card)
        if not candidates:
            return
        chosen = choose_object(
            game,
            controller,
            candidates,
            "Choose an instant or sorcery card with mana value 1",
            source_card=self,
        )
        if chosen is None:
            return
        library.remove(chosen)
        controller.zones[Zone.HAND].add(chosen)
        # Shuffle library
        library.shuffle()
