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
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker —
    Ral — starting loyalty 3.

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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Ral"})
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

        def _plus1_surveil2(game: "GameState") -> None:
            """Surveil 2 — top card first; bin or keep each.

            Limitation: kept cards stay in their current order (no reorder
            choice for the cards left on top).
            """
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            top_cards = list(reversed(library.top(2)))  # top first
            for card in top_cards:
                if controller.choose_yes_no(
                    f"Surveil — put {card.name} into your graveyard?"
                ):
                    move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

        def _minus1_discards(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", None) or []
            for target_player in targets:
                if not _is_player(target_player):
                    continue
                hand_cards = target_player.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                chosen = target_player.choose_card(
                    hand_cards, "Choose a card to discard"
                )
                if chosen is None or not target_player.zones[Zone.HAND].contains(chosen):
                    chosen = hand_cards[-1]
                discard(game, target_player, chosen)

        def _minus2_reanimate(game: "GameState") -> None:
            """Return target creature card (MV <= 3) from your graveyard
            to the battlefield."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = getattr(pw, "chosen_targets", None) or []
            card = targets[0] if targets else None
            if card is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(card):
                return  # fizzles — target left the graveyard
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return
            cost = getattr(card, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7_coin_flips(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            targets = getattr(pw, "chosen_targets", None) or []
            opponent = targets[0] if targets else None
            if opponent is None or not _is_player(opponent):
                return
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            opponent.skip_turns += heads  # X = 0 skips nothing

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1_surveil2,
                           description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1_discards,
                           description="−1: Any number of target players "
                           "each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2_reanimate,
                           description="−2: Return target creature card "
                           "with mana value 3 or less from your graveyard "
                           "to the battlefield."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7_coin_flips,
                           description="−7: Flip five coins. Target "
                           "opponent skips their next X turns (X = heads)."),
        ]
