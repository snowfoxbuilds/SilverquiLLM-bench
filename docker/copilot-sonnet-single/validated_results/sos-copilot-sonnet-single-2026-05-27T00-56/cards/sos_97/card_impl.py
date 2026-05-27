"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral — 3 loyalty.

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
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from your graveyard "
            "to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where X is the "
            "number of coins that came up heads.",
        )
        super().__init__(**kwargs)
        # Targets set by callers before invoking ability effects
        self._resolve_target: Any = None
        self._resolve_targets: list[Any] = []

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2: look at the top 2 cards of the controller's library
            and put any number into the graveyard; the rest stay on top."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            cards = library.get_all()
            if not cards:
                return
            top_cards = cards[-min(2, len(cards)):]
            # Iterate from the card closest to the top downward
            for card in reversed(top_cards):
                put_in_gy = controller.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                )
                if put_in_gy:
                    library.remove(card)
                    controller.zones[Zone.GRAVEYARD].add(card)

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            targets = pw._resolve_targets
            for player in targets:
                hand = player.zones[Zone.HAND]
                hand_cards = hand.get_all()
                if hand_cards:
                    # Discard the top (last) card
                    card = hand_cards[-1]
                    hand.remove(card)
                    player.zones[Zone.GRAVEYARD].add(card)

        def _minus2(game: Any) -> None:
            """Return target creature card with MV ≤ 3 from your graveyard to the battlefield."""
            target = pw._resolve_target
            if target is None:
                return
            controller = pw.controller
            if controller is None:
                return
            # Only reanimate if the card is still in the graveyard
            gy = controller.zones[Zone.GRAVEYARD]
            if not gy.contains(target):
                return
            # Check it is a creature
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            # Check MV ≤ 3
            mv = getattr(target.mana_cost, "cmc", 0) if hasattr(target, "mana_cost") else 0
            if mv > 3:
                return
            gy.remove(target)
            game.get_battlefield(controller).add(target)

        def _minus7(game: Any) -> None:
            """Flip five coins; target opponent skips next X turns (X = heads)."""
            target = pw._resolve_target
            if target is None:
                return
            heads = sum(1 for _ in range(5) if random.random() < 0.5)
            current = getattr(target, "turns_to_skip", 0)
            target.turns_to_skip = current + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description=(
                    "−2: Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description=(
                    "−7: Flip five coins. Target opponent skips their next X turns, "
                    "where X is the number of coins that came up heads."
                ),
            ),
        ]
