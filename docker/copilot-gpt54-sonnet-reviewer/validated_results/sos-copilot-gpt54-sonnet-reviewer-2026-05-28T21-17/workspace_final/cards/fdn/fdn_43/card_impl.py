"""Card implementation for Inspiration from Beyond."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class InspirationFromBeyond(Sorcery):
    """Inspiration from Beyond — {2}{U} — Sorcery.

    Mill three cards, then return an instant or sorcery card from your
    graveyard to your hand.
    Flashback {5}{U}{U}

    FDN collector number 43.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inspiration from Beyond")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Mill three cards, then return an instant or sorcery card from "
            "your graveyard to your hand.\n"
            "Flashback {5}{U}{U}",
        )
        super().__init__(**kwargs)
        # ENGINE LIMITATION: Flashback is not natively supported by the engine.
        # We store the cost for potential future use.
        self.flashback_cost = ManaCost.parse("{5}{U}{U}")

    def on_resolve(self, game: "GameState") -> None:
        """Mill 3, then return an instant or sorcery from graveyard to hand."""
        from engine.game import mill_cards
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # Mill 3 in deterministic top-first order.
        mill_cards(game, controller, 3)

        # Return an instant or sorcery card from graveyard to hand
        graveyard = controller.zones[Zone.GRAVEYARD]
        eligible = [
            c for c in graveyard.get_all()
            if CardType.INSTANT in getattr(c, "card_types", set())
            or CardType.SORCERY in getattr(c, "card_types", set())
        ]
        if not eligible:
            return

        try:
            chosen = controller.choose_card(
                eligible,
                "Choose an instant or sorcery card to return to your hand",
            )
        except Exception:
            chosen = eligible[0] if eligible else None

        if chosen is not None and chosen in list(graveyard.get_all()):
            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.HAND)
