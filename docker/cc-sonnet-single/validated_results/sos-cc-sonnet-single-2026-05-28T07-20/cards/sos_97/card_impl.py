"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral — 3 loyalty.

    +1: Surveil 2.
    -1: Any number of target players each discard a card.
    -2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
    -7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins
        that came up heads.
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
            "-1: Any number of target players each discard a card.\n"
            "-2: Return target creature card with mana value 3 or less from your graveyard "
            "to the battlefield.\n"
            "-7: Flip five coins. Target opponent skips their next X turns, where X is the "
            "number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2: look at top 2 cards; put any number into graveyard, rest on top."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]

            # Get the top 2 cards (or fewer if library is small)
            n = min(2, len(library))
            if n == 0:
                return

            # top(n) returns bottom-to-top order; get them from the top
            top_cards = library.top(n)
            # Remove top cards from library (in reverse order so top is removed first)
            for card in reversed(top_cards):
                library.remove(card)

            # For each card, ask the player if they want to put it in the graveyard
            keep_on_library = []
            for card in reversed(top_cards):  # process top card first
                try:
                    send_to_gy = controller.choose_yes_no(
                        f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                    )
                except Exception:
                    send_to_gy = False
                if send_to_gy:
                    graveyard.add(card)
                else:
                    keep_on_library.append(card)

            # Put the kept cards back on top in the order the player wants them
            # For simplicity, keep them in the same relative order (bottom-to-top)
            for card in reversed(keep_on_library):
                library.add(card)

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            targets = getattr(pw, "chosen_targets", [])
            for player in targets:
                hand = player.zones[Zone.HAND]
                hand_cards = hand.get_all()
                if not hand_cards:
                    continue
                try:
                    card_to_discard = player.choose_card(hand_cards, "Choose a card to discard")
                except Exception:
                    card_to_discard = hand_cards[0]
                if card_to_discard is not None and hand.contains(card_to_discard):
                    hand.remove(card_to_discard)
                    player.zones[Zone.GRAVEYARD].add(card_to_discard)

        def _minus2(game: Any) -> None:
            """Return target creature card with mana value ≤3 from graveyard to battlefield."""
            from engine.zones import move_to_zone

            targets = getattr(pw, "chosen_targets", [])
            if not targets:
                return
            target = targets[0]
            # Validate: must be a creature card with mana value ≤ 3
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mv = getattr(target, "mana_cost", None)
            if mv is None:
                return
            if mv.cmc > 3:
                return

            controller = pw.controller
            if controller is None:
                return

            # Verify the card is in the controller's graveyard (not any opponent's)
            if not controller.zones[Zone.GRAVEYARD].contains(target):
                return

            # Set controller before moving so the creature enters under the right player
            target.controller = controller
            if target.owner is None:
                target.owner = controller

            # Use the engine helper so ETB triggers, register_triggers, and
            # register_replacement_effects all fire correctly.
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """Flip 5 coins; target opponent skips their next X turns (X = heads)."""
            targets = getattr(pw, "chosen_targets", [])
            # Count heads: random.random() < 0.5 → heads
            heads = sum(1 for _ in range(5) if random.random() < 0.5)
            if targets:
                opponent = targets[0]
                opponent.turns_to_skip = getattr(opponent, "turns_to_skip", 0) + heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="-1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="-2: Return target creature card with mana value 3 or less from "
                "your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="-7: Flip five coins. Target opponent skips their next X turns.",
            ),
        ]
