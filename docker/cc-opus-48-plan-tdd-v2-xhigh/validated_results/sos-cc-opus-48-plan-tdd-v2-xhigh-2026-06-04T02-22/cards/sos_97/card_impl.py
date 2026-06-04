"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    mc = getattr(card, "mana_cost", None)
    return mc.cmc if mc is not None else 0


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — Legendary Planeswalker — Ral.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns, where X
        is the number of coins that came up heads.

    SOS collector number 97.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {
            Supertype.LEGENDARY
        }
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

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            from engine.game import surveil

            ctrl = pw.controller
            if ctrl is not None:
                surveil(game, ctrl, 2)

        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            ctrl = pw.controller
            if ctrl is None:
                return
            for pl in game.players:
                name = getattr(pl, "name", "player")
                if not ctrl.choose_yes_no(f"Target {name} to discard a card?"):
                    continue
                hand = game.get_hand(pl)
                cards = list(hand.get_all())
                if not cards:
                    continue
                chosen = pl.choose_card(cards, "Choose a card to discard")
                if chosen is not None:
                    discard(game, pl, chosen)

        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            gy = game.get_graveyard(ctrl)
            eligible = [
                c for c in gy.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and _mana_value(c) <= 3
            ]
            if not eligible:
                return
            chosen = ctrl.choose_card(
                eligible, "Return a creature card (mana value 3 or less)"
            )
            if chosen is None:
                return
            move_to_zone(game, chosen, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            from engine.game import flip_coin

            ctrl = pw.controller
            if ctrl is None:
                return
            heads = sum(1 for _ in range(5) if flip_coin(game, ctrl))
            opp = next((p for p in game.players if p is not ctrl), None)
            if opp is None:
                return
            seat = game.players.index(opp)
            game.skipped_turns[seat] = game.skipped_turns.get(seat, 0) + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description="+1: Surveil 2."),
            LoyaltyAbility(
                loyalty_cost=-1, effect=_minus1,
                description="−1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2, effect=_minus2,
                description="−2: Return target creature card with mana value 3 "
                "or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7, effect=_minus7,
                description="−7: Flip five coins. Target opponent skips their "
                "next X turns (X = heads).",
            ),
        ]
