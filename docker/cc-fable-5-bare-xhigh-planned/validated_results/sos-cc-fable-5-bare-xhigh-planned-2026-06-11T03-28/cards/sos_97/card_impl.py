"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and hasattr(obj, "zones")


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
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
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard "
            "a card.\n−2: Return target creature card with mana value 3 or "
            "less from your graveyard to the battlefield.\n−7: Flip five "
            "coins. Target opponent skips their next X turns, where X is "
            "the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """Surveil 2: look at the top two cards, bin any number, leave
            the rest on top (in their original order — a deliberate
            simplification of 'in any order')."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            # top(2) is bottom-to-top; look at them top-down.
            for card in reversed(library.top(2)):
                if controller.choose_yes_no(
                    f"Surveil: put {getattr(card, 'name', 'card')} into "
                    "your graveyard?"
                ):
                    library.remove(card)
                    graveyard.add(card)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            for player in getattr(pw, "chosen_targets", None) or []:
                if not _is_player(player):
                    continue
                cards_in_hand = player.zones[Zone.HAND].get_all()
                if not cards_in_hand:
                    continue
                chosen = player.choose_card(cards_in_hand, "Discard a card")
                if chosen is not None:
                    discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            """Return target creature card with MV <= 3 from your graveyard
            to the battlefield."""
            from engine.zones import move_to_zone

            controller = pw.controller
            targets = getattr(pw, "chosen_targets", None) or []
            card = targets[0] if targets else None
            if card is None or controller is None:
                return
            if not game.get_graveyard(controller).contains(card):
                return  # target left the graveyard — fizzle
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return
            cost = getattr(card, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            targets = getattr(pw, "chosen_targets", None) or []
            opponent = targets[0] if targets else None
            if not _is_player(opponent):
                return
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                opponent.skip_turns = getattr(opponent, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1,
                           description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1,
                           description="−1: Any number of target players "
                                       "each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2,
                           description="−2: Return target creature card "
                                       "with mana value 3 or less from "
                                       "your graveyard to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7,
                           description="−7: Flip five coins. Target "
                                       "opponent skips their next X turns, "
                                       "where X is the number of heads."),
        ]
