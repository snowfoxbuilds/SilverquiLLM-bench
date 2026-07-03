"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return cost.cmc if cost is not None else 0


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
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Ral"})
        kwargs.setdefault(
            "rules_text",
            "+1: Surveil 2.\n−1: Any number of target players each discard a "
            "card.\n−2: Return target creature card with mana value 3 or less "
            "from your graveyard to the battlefield.\n−7: Flip five coins. "
            "Target opponent skips their next X turns, where X is the number "
            "of coins that came up heads.",
        )
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: "GameState") -> None:
            """Surveil 2."""
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            # Look at the top 2; for each (top first), put into graveyard or
            # leave on top.
            for card in reversed(library.top(2)):
                try:
                    to_gy = ctrl.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into "
                        f"your graveyard? (no keeps it on top)"
                    )
                except Exception:
                    to_gy = False
                if to_gy and library.contains(card):
                    library.remove(card)
                    graveyard.add(card)

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            targets = getattr(pw, "chosen_targets", None) or []
            for tp in targets:
                if tp not in game.players:
                    continue
                hand_cards = list(tp.zones[Zone.HAND].get_all())
                if not hand_cards:
                    continue
                try:
                    chosen = tp.choose_card(hand_cards, "discard a card")
                except Exception:
                    chosen = hand_cards[0]
                if chosen is None:
                    chosen = hand_cards[0]
                if tp.zones[Zone.HAND].contains(chosen):
                    discard(game, tp, chosen)

        def _minus2(game: "GameState") -> None:
            """Reanimate a creature card with mana value <= 3 from your gy."""
            from engine.zones import move_to_zone

            ctrl = pw.controller
            targets = getattr(pw, "chosen_targets", None) or []
            target = targets[0] if targets else None
            if ctrl is None or target is None:
                return
            gy = ctrl.zones[Zone.GRAVEYARD]
            if not gy.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if _mana_value(target) > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips their next X turns."""
            ctrl = pw.controller
            targets = getattr(pw, "chosen_targets", None) or []
            target_opp = targets[0] if targets else None
            if target_opp is None or target_opp not in game.players:
                target_opp = next(
                    (p for p in game.players if p is not ctrl), None
                )
            if target_opp is None:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                import random

                rng = random.Random()
                game.rng = rng
            heads = sum(rng.randint(0, 1) for _ in range(5))
            target_opp.skip_turns = getattr(target_opp, "skip_turns", 0) + heads

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
                "next X turns (X = heads).",
            ),
        ]
