"""Card implementation for Curator of Destinies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class CuratorOfDestinies(Creature):
    """Curator of Destinies — {4}{U}{U} — 5/5 — Sphinx — Flying.

    This spell can't be countered.
    Flying
    When this creature enters, look at the top five cards of your library
    and separate them into a face-down pile and a face-up pile. An opponent
    chooses one of those piles. Put that pile into your hand and the other
    into your graveyard.

    FDN collector number 34.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Curator of Destinies")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault("subtypes", {"Sphinx"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "This spell can't be countered.\nFlying\n"
            "When this creature enters, look at the top five cards of your "
            "library and separate them into a face-down pile and a face-up "
            "pile. An opponent chooses one of those piles. Put that pile into "
            "your hand and the other into your graveyard.",
        )
        super().__init__(**kwargs)
        # ENGINE LIMITATION: "can't be countered" is not enforced by the
        # engine's stack resolution. We set a flag for potential future use.
        self.uncounterable = True

    def on_resolve(self, game: "GameState") -> None:
        """ETB: Fact or Fiction–style pile split."""
        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        cards = list(library.get_all())
        if not cards:
            return
        # Top 5 cards (top is end of list)
        top_cards = cards[-min(5, len(cards)):]

        # Controller separates into two piles.
        # ENGINE LIMITATION: The engine doesn't have a "separate into piles"
        # UI action. We use choose_card() to let the controller pick cards
        # for pile A (face-up); the rest go to pile B (face-down).
        pile_a: list[Any] = []
        remaining = list(top_cards)
        while remaining:
            chosen = controller.choose_card(
                remaining,
                "Choose a card for the face-up pile (or None to stop)",
            )
            if chosen is None or chosen not in remaining:
                break
            pile_a.append(chosen)
            remaining.remove(chosen)
        pile_b = remaining

        # Opponent chooses a pile
        opponent = None
        for player in game.players:
            if player is not controller:
                opponent = player
                break
        if opponent is None:
            opponent = controller

        # Opponent chooses: True = pile A (face-up) goes to hand
        choose_a = opponent.choose_yes_no(
            "Choose: Yes = face-up pile to hand, No = face-down pile to hand"
        )
        if choose_a:
            hand_pile = pile_a
            gy_pile = pile_b
        else:
            hand_pile = pile_b
            gy_pile = pile_a

        # Move cards
        for card in hand_pile:
            library.remove(card)
            controller.zones[Zone.HAND].add(card)
        for card in gy_pile:
            library.remove(card)
            controller.zones[Zone.GRAVEYARD].add(card)
