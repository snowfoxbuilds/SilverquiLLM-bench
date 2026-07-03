"""Card implementation for Banishing Betrayal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BanishingBetrayal(Instant):
    """Banishing Betrayal — {1}{U} — Instant.

    Return target nonland permanent to its owner's hand. Surveil 1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Banishing Betrayal")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}"))
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [TargetRequirement(
            filter_fn=lambda obj: CardType.LAND not in getattr(obj, "card_types", set()),
            description="target nonland permanent",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]

        # Bounce target to owner's hand
        owner = getattr(target, "owner", None)
        if owner is None:
            return

        # Remove from battlefield
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                bf.remove(target)
                break

        # Add to owner's hand
        game.get_hand(owner).add(target)

        # Surveil 1 for the controller
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        cards = library.get_all()
        if cards:
            top_card = cards[-1]
            library.remove(top_card)
            game.get_graveyard(controller).add(top_card)
