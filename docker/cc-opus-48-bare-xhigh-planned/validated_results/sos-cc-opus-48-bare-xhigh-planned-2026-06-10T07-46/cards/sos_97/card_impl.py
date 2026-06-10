"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    cost = getattr(card, "mana_cost", None)
    return getattr(cost, "cmc", 0) if cost is not None else 0


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

    def _targets(self) -> list:
        return list(getattr(self, "chosen_targets", []) or [])

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        # +1: Surveil 2
        def _plus1(game: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            # Look at the top 2; bin any number, keep the rest on top.
            top_cards = list(reversed(library.top(2)))  # top first
            for card in top_cards:
                if not library.contains(card):
                    continue
                try:
                    bin_it = ctrl.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into your "
                        "graveyard?"
                    )
                except Exception:
                    bin_it = False
                if bin_it:
                    library.remove(card)
                    graveyard.add(card)

        # −1: Any number of target players each discard a card
        def _minus1(game: "GameState") -> None:
            from engine.game import discard

            for tp in pw._targets():
                if tp is None:
                    continue
                hand_cards = tp.zones[Zone.HAND].get_all()
                if not hand_cards:
                    continue
                try:
                    chosen = tp.choose_card(hand_cards, "discard a card (Ral −1)")
                except Exception:
                    chosen = hand_cards[0]
                if chosen is not None and tp.zones[Zone.HAND].contains(chosen):
                    discard(game, tp, chosen)

        # −2: Reanimate a creature card with MV ≤ 3 from your graveyard
        def _minus2(game: "GameState") -> None:
            from engine.zones import move_to_zone

            ctrl = pw.controller
            if ctrl is None:
                return
            target = (pw._targets() or [None])[0]
            if target is None:
                return
            if not ctrl.zones[Zone.GRAVEYARD].contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            if _mana_value(target) > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # −7: Flip five coins, target opponent skips their next X turns
        def _minus7(game: "GameState") -> None:
            target = (pw._targets() or [None])[0]
            if target is None:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                import random

                rng = random.Random()
                game.rng = rng
            heads = sum(rng.randint(0, 1) for _ in range(5))
            current = getattr(target, "skip_turns", 0)
            target.skip_turns = current + heads

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
                description="−2: Reanimate a creature card with mana value ≤ 3.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins; target opponent skips X turns.",
            ),
        ]
