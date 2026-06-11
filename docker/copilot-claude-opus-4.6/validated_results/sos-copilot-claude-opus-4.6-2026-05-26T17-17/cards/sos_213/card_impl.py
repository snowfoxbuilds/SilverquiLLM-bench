"""Card implementation for Proctor's Gaze."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class ProctorsGaze(Instant):
    """Proctor's Gaze — {2}{G}{U} — Instant.

    Return up to one target nonland permanent to its owner's hand.
    Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Proctor's Gaze")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        super().__init__(**kwargs)
        self.chosen_targets: list[Any] = []

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner

        # Bounce up to one target nonland permanent
        for target in self.chosen_targets:
            owner = target.owner
            bf = game.get_battlefield(owner)
            hand = game.get_hand(owner)
            if target in bf:
                bf.remove(target)
                hand.add(target)

        # Search library for a basic land, put onto battlefield tapped, shuffle
        library = game.get_library(controller)
        bf = game.get_battlefield(controller)

        basic_land = None
        for card in list(library):
            if getattr(card, "is_basic_land", False):
                basic_land = card
                break

        if basic_land is not None:
            library.remove(basic_land)
            basic_land.is_tapped = True
            bf.add(basic_land)

        # Shuffle library
        library.shuffle()
        # Track that library was shuffled
        if not hasattr(game, '_libraries_shuffled'):
            game._libraries_shuffled = set()
        game._libraries_shuffled.add(id(controller))
