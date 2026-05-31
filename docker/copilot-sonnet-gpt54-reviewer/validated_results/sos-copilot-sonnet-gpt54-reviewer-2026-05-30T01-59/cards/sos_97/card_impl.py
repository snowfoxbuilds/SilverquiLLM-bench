"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """+1: Surveil 2.
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
            "\u22121: Any number of target players each discard a card.\n"
            "\u22122: Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
            "\u22127: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2: look at top 2 cards, put any number into graveyard, rest on top."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            all_cards = library.get_all()
            if not all_cards:
                return
            count = min(2, len(all_cards))
            # Top cards are at the end of the list (index -1 = top)
            top_cards = all_cards[-count:]
            for card in reversed(top_cards):
                library.remove(card)

            # Let controller choose which to put in graveyard (may be none or all)
            to_graveyard = getattr(pw, "_surveil_to_graveyard", None)
            if to_graveyard is None:
                # Default: try to ask controller
                try:
                    to_graveyard = controller.choose_cards(
                        top_cards, "Choose cards to put into graveyard (surveil 2)"
                    )
                except Exception:
                    to_graveyard = []
            # Validate chosen cards are actually in top_cards
            if to_graveyard is None:
                to_graveyard = []
            valid_graveyard = [c for c in to_graveyard if c in top_cards]
            keep_on_top = [c for c in top_cards if c not in valid_graveyard]

            for card in valid_graveyard:
                graveyard.add(card)
            # Put keep_on_top back (first card in list goes to top last => reverse order)
            for card in reversed(keep_on_top):
                library.add(card, position="top")

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card."""
            targets = getattr(pw, "_resolve_targets", None) or []
            if not targets:
                # Fallback: use single target
                t = getattr(pw, "_resolve_target", None)
                if t is not None:
                    targets = [t]
            for target_player in targets:
                from engine.game import discard as _discard
                hand = target_player.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                try:
                    chosen = target_player.choose_card(
                        cards_in_hand, "discard a card"
                    )
                except Exception:
                    chosen = cards_in_hand[-1]
                if chosen is not None and hand.contains(chosen):
                    _discard(game, target_player, chosen)
                elif cards_in_hand:
                    _discard(game, target_player, cards_in_hand[-1])

        def _minus2(game: Any) -> None:
            """Return target creature with MV ≤3 from your graveyard to battlefield."""
            controller = pw.controller
            if controller is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            # Validate: must be creature card with MV ≤3 in controller's graveyard
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mv = getattr(target, "mana_cost", None)
            if mv is not None and mv.cmc > 3:
                return
            # Move to battlefield
            graveyard.remove(target)
            battlefield = controller.zones[Zone.BATTLEFIELD]
            battlefield.add(target)
            if hasattr(target, "summoning_sick"):
                target.summoning_sick = True

        def _minus7(game: Any) -> None:
            """Flip 5 coins, target opponent skips next X turns (X = heads)."""
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            # Use engine random or override for testing
            flip_fn = getattr(pw, "_coin_flip_fn", None) or (lambda: random.randint(0, 1))
            heads = sum(flip_fn() for _ in range(5))
            if heads > 0 and hasattr(target, "turns_to_skip"):
                target.turns_to_skip = getattr(target, "turns_to_skip", 0) + heads

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
                description="\u22122: Return target creature with MV \u22643 from your graveyard to battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="\u22127: Flip 5 coins; target opponent skips next X turns.",
            ),
        ]
