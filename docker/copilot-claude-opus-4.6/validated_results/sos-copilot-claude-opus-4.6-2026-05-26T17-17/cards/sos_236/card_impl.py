"""Card implementation for Suspend Aggression."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SuspendAggression(Instant):
    """Suspend Aggression — {1}{R}{W} — Instant.

    Exile target nonland permanent and the top card of your library.
    For each of those cards, its owner may play it until the end of their next turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Suspend Aggression")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target nonland permanent and the top card of your library. "
            "For each of those cards, its owner may play it until the end of their next turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        """Target nonland permanent."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.LAND not in getattr(obj, "card_types", set()),
                description="target nonland permanent",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Exile target and top card of library, granting impulsive play."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        controller = self.controller or self.owner
        if controller is None:
            return

        # Exile the target from battlefield
        target_controller = getattr(target, "controller", controller)
        bf = game.get_battlefield(target_controller)
        if target in bf.get_all():
            bf.remove(target)
            controller.zones[Zone.EXILE].add(target)

        # Exile top card of controller's library
        library = controller.zones[Zone.LIBRARY]
        if len(library.get_all()) > 0:
            top_cards = library.top(1)
            if top_cards:
                top_card = top_cards[0]
                library.remove(top_card)
                controller.zones[Zone.EXILE].add(top_card)
