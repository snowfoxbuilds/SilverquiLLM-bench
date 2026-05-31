"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — 3 loyalty.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where
        X is the number of coins that came up heads.
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
            "\u22121: Any number of target players each discard a card.\n"
            "\u22122: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n"
            "\u22127: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2 — look at top 2 cards; put any into graveyard, rest back on top."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            all_cards = library.get_all()
            count = min(2, len(all_cards))
            if count == 0:
                return
            # Top of library is the end of the list.
            top_cards = all_cards[-count:]

            # Ask controller to choose which cards to put in graveyard.
            # If the player has a choose_cards method, use it; otherwise
            # default to putting none in the graveyard (keep all on top).
            surveil_to_gy: list[Any] = []
            try:
                chosen = controller.choose_cards(
                    top_cards, "Surveil: choose cards to put into graveyard"
                )
                if chosen is not None:
                    surveil_to_gy = list(chosen)
            except Exception:
                surveil_to_gy = []

            keep_on_top = [c for c in top_cards if c not in surveil_to_gy]

            # Remove all surveiled cards from library and move to graveyard.
            for card in surveil_to_gy:
                library.remove(card)
                graveyard.add(card)

            # Cards kept on top stay in library (already there); nothing to do
            # unless we want to reorder — for simplicity keep original order.

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard as _discard
            targets = getattr(pw, "chosen_targets", None) or []
            # targets may be a list of players
            for target in targets:
                if not hasattr(target, "zones"):
                    continue
                hand = target.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                # Try to let the player choose which card to discard.
                card_to_discard = None
                try:
                    card_to_discard = target.choose_card(
                        cards_in_hand, "Choose a card to discard"
                    )
                except Exception:
                    pass
                if card_to_discard is None:
                    card_to_discard = cards_in_hand[-1]
                _discard(game, target, card_to_discard)

        def _minus2(game: Any) -> None:
            """Return target creature card with mana value ≤ 3 from your graveyard to battlefield."""
            from engine.zones import move_to_zone
            controller = pw.controller
            if controller is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            # Validate: must be a creature card in controller's graveyard with MV ≤ 3.
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            card_types = getattr(target, "card_types", set())
            if CardType.CREATURE not in card_types:
                return
            mana_cost = getattr(target, "mana_cost", None)
            mv = mana_cost.cmc if mana_cost is not None else 0
            if mv > 3:
                return
            target.owner = getattr(target, "owner", controller)
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            """Flip 5 coins; target opponent skips their next X turns (X = heads)."""
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            # Flip 5 coins.
            heads = sum(random.randint(0, 1) for _ in range(5))
            if heads == 0:
                return
            # Find the target opponent's player index.
            target_index = None
            for i, p in enumerate(game.players):
                if p is target:
                    target_index = i
                    break
            if target_index is None:
                return
            # Make that opponent skip their next `heads` turns by inserting
            # them into extra_turns — but we need them to NOT take those turns.
            # We implement turn-skipping by tracking skipped turns on the player.
            if not hasattr(target, "turns_to_skip"):
                target.turns_to_skip = 0
            target.turns_to_skip += heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="\u22121: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="\u22122: Return target creature card with MV \u22643 from your graveyard to battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="\u22127: Flip 5 coins; target opponent skips next X turns (X = heads).",
            ),
        ]
