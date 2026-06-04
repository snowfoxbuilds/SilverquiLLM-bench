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
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n"
            "−1: Any number of target players each discard a card.\n"
            "−2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "−7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def _flip_five_coins(self) -> int:
        """Flip five coins and return the number of heads (0–5).

        Isolated so tests can override the result deterministically by
        assigning a zero-argument callable to the instance attribute.
        """
        return sum(1 for _ in range(5) if random.random() < 0.5)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            # Topmost card is the last element; look at the top two.
            top_two = list(reversed(library.get_all()))[:2]
            for card in top_two:
                if not library.contains(card):
                    continue
                if ctrl.choose_yes_no(
                    f"Surveil 2: put {getattr(card, 'name', 'card')} into your "
                    "graveyard?"
                ):
                    library.remove(card)
                    ctrl.zones[Zone.GRAVEYARD].add(card)

        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None)
            if not targets:
                return
            for player in targets:
                cards = list(player.zones[Zone.HAND].get_all())
                if not cards:
                    continue
                chosen = player.choose_card(cards, "Choose a card to discard")
                if chosen is None:
                    continue
                discard(game, player, chosen)

        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cost = getattr(target, "mana_cost", None)
            if cost is None or cost.cmc > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            if hasattr(target, "summoning_sick"):
                target.summoning_sick = True

        def _minus7(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            opponent = getattr(pw, "_resolve_target", None)
            heads = pw._flip_five_coins()
            if opponent is None or heads <= 0:
                return
            try:
                opp_index = game.players.index(opponent)
            except ValueError:
                return
            game.skipped_turns[opp_index] = (
                game.skipped_turns.get(opp_index, 0) + heads
            )

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
                description="−2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their "
                "next X turns, where X is the number of coins that came up heads.",
            ),
        ]
