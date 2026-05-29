"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        """Return the four loyalty abilities."""
        return [
            LoyaltyAbility(
                loyalty_cost=1,
                effect=self._plus_one,
                description="Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=self._minus_one,
                description="Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=self._minus_two,
                description="Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=self._minus_seven,
                description="Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
            ),
        ]

    def _plus_one(self, game: "GameState") -> None:
        """Surveil 2: look at top 2 cards; put any into graveyard, rest on top."""
        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        # Take up to 2 cards from the top of the library
        top_cards = library.top(2)
        if not top_cards:
            return

        # Remove these cards from the library temporarily
        for card in top_cards:
            library.remove(card)

        # For each card, ask the controller whether to put it in the graveyard
        keep_on_top: list[Any] = []
        graveyard = controller.zones[Zone.GRAVEYARD]

        for card in top_cards:
            send_to_gy = controller.choose_yes_no(
                f"Put {getattr(card, 'name', repr(card))} into your graveyard?"
            )
            if send_to_gy:
                graveyard.add(card)
            else:
                keep_on_top.append(card)

        # Put kept cards back on top (in original order — first surveiled is bottom of kept)
        for card in keep_on_top:
            library.add(card, position="top")

    def _minus_one(self, game: "GameState") -> None:
        """Any number of target players each discard a card."""
        targets = getattr(self, "chosen_targets", [])
        for player in targets:
            hand = game.get_hand(player)
            hand_cards = list(hand.get_all())
            if not hand_cards:
                continue
            # Use discard from engine
            from engine.game import discard as engine_discard
            # Player discards one card — use choose_card to pick which
            card_to_discard = player.choose_card(hand_cards, "Choose a card to discard")
            if card_to_discard is not None and hand.contains(card_to_discard):
                engine_discard(game, player, card_to_discard)

    def _minus_two(self, game: "GameState") -> None:
        """Return target creature card with MV ≤ 3 from YOUR graveyard to the battlefield."""
        controller = self.controller
        if controller is None:
            return

        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        target = targets[0]

        # Only reanimate if the card is in the controller's graveyard
        controller_gy = game.get_graveyard(controller)
        if not controller_gy.contains(target):
            return

        # Validate it's a creature with MV ≤ 3
        card_types = getattr(target, "card_types", set())
        if CardType.CREATURE not in card_types:
            return

        mana_cost = getattr(target, "mana_cost", None)
        mv = 0
        if mana_cost is not None:
            mv = getattr(mana_cost, "cmc", 0)
            if callable(mv):
                mv = mv()
        if mv > 3:
            return

        # Move from graveyard to battlefield
        from engine.zones import move_to_zone
        target.controller = controller
        move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

    def _minus_seven(self, game: "GameState") -> None:
        """Flip 5 coins; target opponent skips their next X turns (X = heads).

        # UNVERIFIED: actual turn-skipping integration may need further testing
        """
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return

        opponent = targets[0]

        # Flip 5 coins — use random.randint(0, 1); 1 = heads
        heads = sum(1 for _ in range(5) if random.randint(0, 1) == 1)

        # Add heads to the opponent's turns_to_skip counter
        current = getattr(opponent, "turns_to_skip", 0)
        opponent.turns_to_skip = current + heads
