"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins.  Target opponent skips their next X turns, where
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

    def _chosen_targets(self) -> list[Any]:
        return list(getattr(self, "chosen_targets", None) or [])

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1_surveil(game: GameState) -> None:
            """Surveil 2: look at top 2; each may go to the graveyard."""
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            top_cards = library.top(2)
            for card in reversed(list(top_cards)):  # top of library first
                if controller.choose_yes_no(
                    f"Surveil: put {getattr(card, 'name', 'card')} into "
                    "your graveyard?"
                ):
                    library.remove(card)
                    graveyard.add(card)

        def _minus1_discard(game: GameState) -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            for target in pw._chosen_targets():
                if target not in game.players:
                    continue
                hand = target.zones[Zone.HAND]
                cards_in_hand = hand.get_all()
                if not cards_in_hand:
                    continue
                chosen = target.choose_card(
                    cards_in_hand, "Choose a card to discard"
                )
                if chosen is not None and hand.contains(chosen):
                    discard(game, target, chosen)

        def _minus2_reanimate(game: GameState) -> None:
            """Return target creature card (MV <= 3) from your graveyard."""
            from engine.zones import move_to_zone

            controller = pw.controller
            if controller is None:
                return
            targets = pw._chosen_targets()
            card = targets[0] if targets else None
            if card is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(card):
                return
            if CardType.CREATURE not in getattr(card, "card_types", set()):
                return
            cost = getattr(card, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            card.controller = controller
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7_coin_flips(game: GameState) -> None:
            """Flip five coins; target opponent skips X turns (X = heads)."""
            controller = pw.controller
            targets = pw._chosen_targets()
            target = targets[0] if targets else None
            if target is None or target not in game.players:
                return
            if controller is not None and target is controller:
                return  # must be an opponent
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                target.skip_turns += heads

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1_surveil,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1_discard,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2_reanimate,
                description=(
                    "−2: Return target creature card with mana value 3 or "
                    "less from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7_coin_flips,
                description=(
                    "−7: Flip five coins. Target opponent skips their next "
                    "X turns, where X is the number of heads."
                ),
            ),
        ]
