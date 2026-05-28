"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# UNVERIFIED: surveil card ordering — controller choice not testable in this engine


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty: 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your graveyard
        to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is the
        number of coins that came up heads.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard "
            "to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the "
            "number of coins that came up heads.",
        )
        super().__init__(starting_loyalty=3, **kwargs)
        # Holds the set of cards the controller wants to send to the graveyard
        # during surveil (set by caller before resolution).
        self.chosen_surveil_to_graveyard: list[Any] = []
        # Holds the targets chosen by the controller for abilities (set by caller).
        self.chosen_targets: list[Any] = []

    # ------------------------------------------------------------------
    # Internal ability implementations
    # ------------------------------------------------------------------

    def _surveil(self, game: "GameState", num: int = 2) -> None:
        """Surveil *num*: look at top *num* cards; send chosen to graveyard."""
        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        graveyard = controller.zones[Zone.GRAVEYARD]

        top_cards = library.top(num)
        if not top_cards:
            return

        # Remove all surveiled cards from library.
        for card in top_cards:
            library.remove(card)

        # Send chosen cards to graveyard.
        to_gy = list(self.chosen_surveil_to_graveyard)
        to_keep = [c for c in top_cards if c not in to_gy]

        for card in to_gy:
            if card in top_cards:
                graveyard.add(card)

        # Keep the rest on top of the library (in original order).
        for card in reversed(to_keep):
            library.add(card, position="top")

    def _minus_one_discard(self, game: "GameState") -> None:
        """−1: Each chosen target player discards a card of their choice."""
        from engine.player import ScriptExhaustedError
        from engine.zones import move_to_zone

        for target in list(self.chosen_targets):
            # target is a Player
            hand = target.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if not cards_in_hand:
                continue
            # Ask the target player to choose which card to discard.
            try:
                card = target.choose_card(cards_in_hand, "discard a card")
                if card is None or card not in cards_in_hand:
                    card = cards_in_hand[0]
            except (ScriptExhaustedError, NotImplementedError):
                # Fallback for scripted/deterministic players with no queued choice.
                card = cards_in_hand[0]
            move_to_zone(game, card, Zone.HAND, Zone.GRAVEYARD)

    def _minus_two_reanimate(self, game: "GameState") -> None:
        """−2: Return target creature with MV ≤ 3 from graveyard to battlefield."""
        from engine.zones import move_to_zone

        for target in list(self.chosen_targets):
            # Validate: must be a creature card.
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                continue
            # Validate: MV must be ≤ 3.
            mana_cost = getattr(target, "mana_cost", None)
            if mana_cost is not None:
                cmc = mana_cost.cmc
            else:
                cmc = 0
            if cmc > 3:
                continue
            # Move from graveyard to battlefield.
            controller = self.controller
            if controller is None:
                continue
            gy = controller.zones[Zone.GRAVEYARD]
            if not gy.contains(target):
                continue
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            break  # Only one target for this ability.

    def _minus_seven_coin_flip(self, game: "GameState") -> None:
        """−7: Flip 5 coins. Target opponent skips next X turns (X = heads)."""
        heads = sum(1 for _ in range(5) if random.random() < 0.5)
        for target in list(self.chosen_targets):
            target.turns_to_skip = getattr(target, "turns_to_skip", 0) + heads

    # ------------------------------------------------------------------
    # Loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        """Return the four loyalty abilities for Ral Zarek, Guest Lecturer."""
        return [
            LoyaltyAbility(
                loyalty_cost=1,
                effect=lambda game: self._surveil(game, num=2),
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=lambda game: self._minus_one_discard(game),
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=lambda game: self._minus_two_reanimate(game),
                description=(
                    "−2: Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=lambda game: self._minus_seven_coin_flip(game),
                description=(
                    "−7: Flip five coins. Target opponent skips their next X turns, "
                    "where X is the number of coins that came up heads."
                ),
            ),
        ]

