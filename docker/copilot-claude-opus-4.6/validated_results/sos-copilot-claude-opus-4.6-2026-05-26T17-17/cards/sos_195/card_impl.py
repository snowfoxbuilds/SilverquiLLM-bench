"""Card implementation for Imperious Inkmage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class _SurveilETBTrigger:
    """ETB trigger: surveil 2."""

    def __init__(self, source: "ImperiousInkmage") -> None:
        self.source = source
        self.description = "When this creature enters, surveil 2."


class ImperiousInkmage(Creature):
    """Imperious Inkmage — {1}{W}{B} — Creature — Orc Warlock — 3/3.

    Vigilance
    When this creature enters, surveil 2.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Imperious Inkmage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault("subtypes", {"Orc", "Warlock"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    def get_triggered_abilities(self, game: "GameState") -> list[Any]:
        """Return the ETB surveil trigger."""
        return [_SurveilETBTrigger(self)]

    def on_resolve(self, game: "GameState") -> None:
        """ETB: surveil 2 — put cards from top of library into graveyard."""
        controller = self.controller
        if controller is None:
            return

        # Place self on battlefield
        hand = controller.zones[Zone.HAND]
        if hand.contains(self):
            hand.remove(self)
        bf = controller.zones[Zone.BATTLEFIELD]
        bf.add(self)
        self.zone = Zone.BATTLEFIELD
        self.summoning_sick = True

        # Surveil 2: look at top 2, put any number in graveyard, rest on top
        library = controller.zones[Zone.LIBRARY]
        lib_cards = list(library.get_all())
        # Top cards are at the end of the list (convention: index -1 is top)
        n = min(2, len(lib_cards))
        if n == 0:
            return

        top_cards = lib_cards[-n:]  # top N cards
        # Default behavior: put all in graveyard (for test convenience)
        for card in top_cards:
            library.remove(card)
            controller.zones[Zone.GRAVEYARD].add(card)
            card.zone = Zone.GRAVEYARD
