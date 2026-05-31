"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.game import discard
from engine.types import CardType, ManaCost, Supertype, Zone
from engine.zones import move_to_zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer."""

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

        def _plus1(game: "GameState") -> None:
            controller = pw.controller
            if controller is None:
                return

            library = controller.zones[Zone.LIBRARY]
            top_cards = list(library.top(2))
            for card in reversed(top_cards):
                if not library.contains(card):
                    continue
                put_into_graveyard = controller.choose_yes_no(
                    f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?"
                )
                if put_into_graveyard:
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1(game: "GameState") -> None:
            targets = list(
                getattr(
                    pw,
                    "_resolve_targets",
                    getattr(pw, "chosen_targets", []),
                )
            )
            for player in targets:
                if player is None:
                    continue
                hand = game.get_hand(player)
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen = player.choose_card(cards_in_hand, "Discard a card")
                if chosen in cards_in_hand:
                    discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                chosen_targets = getattr(pw, "chosen_targets", None) or []
                target = chosen_targets[0] if chosen_targets else None
            if target is None:
                return

            controller = pw.controller
            if controller is None:
                return

            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return

            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return

            mana_cost = getattr(target, "mana_cost", None)
            if mana_cost is not None and mana_cost.cmc > 3:
                return

            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            return

        return [
            LoyaltyAbility(loyalty_cost=1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
            ),
        ]
