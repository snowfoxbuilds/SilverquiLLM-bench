"""Card implementation for Ral Zarek, Guest Lecturer (SOS 97)."""

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
    -1: Any number of target players each discard a card.
    -2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    -7: Flip five coins. Target opponent skips their next X turns, where X is
        the number of coins that came up heads.
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
            "-1: Any number of target players each discard a card.\n"
            "-2: Return target creature card with mana value 3 or less from "
            "your graveyard to the battlefield.\n"
            "-7: Flip five coins. Target opponent skips their next X turns, "
            "where X is the number of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            # Surveil 2.
            from engine.game import surveil

            controller = pw.controller
            if controller is None:
                return
            surveil(game, controller, 2)

        def _minus1(game: Any) -> None:
            # Any number of target players each discard a card.
            from engine.game import discard

            targets = getattr(pw, "_resolve_targets", None)
            if targets is None:
                single = getattr(pw, "_resolve_target", None)
                targets = [single] if single is not None else []
            for player in targets:
                if player is None:
                    continue
                hand = game.get_hand(player)
                cards = hand.get_all()
                if not cards:
                    continue
                try:
                    chosen = player.choose_card(cards, "Choose a card to discard")
                except (AttributeError, NotImplementedError):
                    chosen = cards[0]
                if chosen is None:
                    chosen = cards[0]
                discard(game, player, chosen)

        def _minus2(game: Any) -> None:
            # Return target creature card with mana value 3 or less from your
            # graveyard to the battlefield.
            from engine.zones import move_to_zone

            controller = pw.controller
            target = getattr(pw, "_resolve_target", None)
            if controller is None or target is None:
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            mc = getattr(target, "mana_cost", None)
            if mc is not None and getattr(mc, "cmc", 0) > 3:
                return
            graveyard = game.get_graveyard(controller)
            if not graveyard.contains(target):
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: Any) -> None:
            # Flip five coins. Target opponent skips their next X turns, where
            # X is the number of coins that came up heads.
            from engine.game import flip_coin, skip_turns

            target = getattr(pw, "_resolve_target", None)
            if target is None:
                return
            heads = sum(1 for _ in range(5) if flip_coin())
            skip_turns(game, target, heads)

        return [
            LoyaltyAbility(
                loyalty_cost=+1,
                effect=_plus1,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=_minus1,
                description="-1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=_minus2,
                description="-2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="-7: Flip five coins. Target opponent skips their "
                "next X turns, where X is the number of heads.",
            ),
        ]
