"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _surveil(game: "GameState", player: "Player", n: int) -> None:
    """Look at the top *n* cards; put any number into the graveyard, the rest
    stay on top."""
    library = player.zones[Zone.LIBRARY]
    top_cards = list(reversed(library.top(n)))  # top-of-library first
    for card in top_cards:
        if not library.contains(card):
            continue
        if player.choose_yes_no(
            f"Surveil: put {getattr(card, 'name', 'card')} into your graveyard?"
        ):
            from engine.zones import move_to_zone
            move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    Starting loyalty 3.
    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X is
        the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard a "
            "card.\n−2: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n−7: Flip five coins. "
            "Target opponent skips their next X turns, where X is the number of "
            "coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """+1: Surveil 2."""
            controller = pw.controller
            if controller is not None:
                _surveil(game, controller, 2)

        def _minus1(game: "GameState") -> None:
            """−1: Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", None) or []
            for target_player in targets:
                hand = game.get_hand(target_player)
                cards = hand.get_all()
                if not cards:
                    continue
                chosen = target_player.choose_card(cards, "Discard a card")
                if chosen is not None and hand.contains(chosen):
                    discard(game, target_player, chosen)

        def _minus2(game: "GameState") -> None:
            """−2: Reanimate target creature card (MV ≤ 3) from your graveyard."""
            from engine.zones import move_to_zone

            controller = pw.controller
            targets = getattr(pw, "chosen_targets", None) or []
            target = targets[0] if targets else None
            if controller is None or target is None:
                return
            if not game.get_graveyard(controller).contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cost = getattr(target, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """−7: Flip five coins; target opponent skips their next X turns."""
            targets = getattr(pw, "chosen_targets", None) or []
            target = targets[0] if targets else None
            if target is None:
                return
            heads = sum(game.rng.randint(0, 1) for _ in range(5))
            target.skip_turns = getattr(target, "skip_turns", 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1,
                           description="−1: Any number of target players each discard a card."),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2,
                           description="−2: Return target creature (MV ≤ 3) from your graveyard."),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7,
                           description="−7: Flip five coins; target opponent skips X turns."),
        ]
