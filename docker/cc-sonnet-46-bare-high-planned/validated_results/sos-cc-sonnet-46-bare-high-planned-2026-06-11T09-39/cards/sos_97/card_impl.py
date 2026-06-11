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

    Starting loyalty: 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where
        X is the number of coins that came up heads.

    SOS collector number 97.
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
            "−2: Return target creature card with mana value 3 or less from your "
            "graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, where "
            "X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        # ------------------------------------------------------------------
        # +1: Surveil 2
        # ------------------------------------------------------------------
        def _plus1(game: Any) -> None:
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            top_cards = library.top(2)
            if not top_cards:
                return

            gy = controller.zones[Zone.GRAVEYARD]
            for card in reversed(top_cards):  # top card is last, offer in display order
                try:
                    put_in_gy = controller.choose_yes_no(
                        f"Put {getattr(card, 'name', 'card')!r} into your graveyard (surveil)? "
                        f"No = keep on top."
                    )
                except Exception:
                    put_in_gy = False
                if put_in_gy:
                    library.remove(card)
                    gy.add(card)
                # If kept, card stays on top (library is not reordered)

        # ------------------------------------------------------------------
        # −1: Any number of target players each discard a card
        # ------------------------------------------------------------------
        def _minus1(game: Any) -> None:
            controller = pw.controller
            if controller is None:
                return
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", None) or []
            for player in targets:
                hand = player.zones[Zone.HAND]
                cards_in_hand = list(hand.get_all())
                if not cards_in_hand:
                    continue
                try:
                    chosen = player.choose_card(cards_in_hand, "Choose a card to discard")
                except Exception:
                    chosen = cards_in_hand[0] if cards_in_hand else None
                if chosen is not None:
                    discard(game, player, chosen)

        # ------------------------------------------------------------------
        # −2: Reanimate target creature MV ≤ 3 from your graveyard
        # ------------------------------------------------------------------
        def _minus2(game: Any) -> None:
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = getattr(pw, "chosen_targets", None) or []
            if not targets:
                return
            target_card = targets[0]
            gy = controller.zones[Zone.GRAVEYARD]
            if gy.contains(target_card):
                move_to_zone(game, target_card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # ------------------------------------------------------------------
        # −7: Flip 5 coins; opponent skips X turns (X = heads)
        # ------------------------------------------------------------------
        def _minus7(game: Any) -> None:
            controller = pw.controller
            if controller is None:
                return

            targets = getattr(pw, "chosen_targets", None) or []
            if not targets:
                return
            target_opponent = targets[0]

            # Use game.rng for determinism in tests; create if absent.
            rng: random.Random = getattr(game, "rng", None) or random.Random()
            if not hasattr(game, "rng"):
                game.rng = rng

            heads = sum(rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                if not hasattr(target_opponent, "skip_turns"):
                    target_opponent.skip_turns = 0
                target_opponent.skip_turns += heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Return target creature MV ≤ 3 from graveyard to battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip 5 coins; opponent skips next X turns (X = heads).",
            ),
        ]
