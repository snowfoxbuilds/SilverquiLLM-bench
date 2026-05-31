"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — starting loyalty 3.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2: look at top 2 cards; put any number into graveyard, rest on top.
            Simplified: move top 2 cards to graveyard (no player choice).
            """
            controller = pw.controller
            if controller is None:
                return
            library = game.get_library(controller)
            graveyard = game.get_graveyard(controller)
            # Collect top 2 cards (last 2 in the internal list, top-of-library first)
            top_cards = library.top(2)
            for card in reversed(top_cards):
                library.remove(card)
                graveyard.add(card)

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard
            targets = getattr(pw, "_resolve_targets", None) or []
            for player in targets:
                hand = game.get_hand(player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    card = player.choose_card(cards_in_hand, "discard a card")
                except Exception:
                    card = cards_in_hand[-1]
                discard(game, player, card)

        def _minus2(game: Any) -> None:
            """Return target creature card with mana value 3 or less from your graveyard to the battlefield."""
            from engine.zones import move_to_zone
            target = getattr(pw, "_resolve_target", None)
            controller = pw.controller
            if target is None or controller is None:
                return
            # Move the card from graveyard to battlefield
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """Flip five coins. Target opponent skips their next X turns, where X is heads."""
            heads = sum(1 for _ in range(5) if random.random() < 0.5)
            target = getattr(pw, "_resolve_target", None)
            if target is not None and heads > 0:
                current = getattr(target, "turns_to_skip", 0)
                target.turns_to_skip = current + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description="−7: Flip five coins. Target opponent skips their next X turns, where X is heads."),
        ]
