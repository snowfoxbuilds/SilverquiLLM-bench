"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _chosen_targets(pw: Any) -> list[Any]:
    return list(getattr(pw, "chosen_targets", None) or [])


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

    Loyalty-ability targets are read from ``self.chosen_targets`` (set by the
    activation's targets / by test setup), as directed by the build plan.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ral Zarek, Guest Lecturer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("starting_loyalty", 3)
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
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
            """Surveil 2: look at the top 2 cards, bin any number, keep the rest."""
            ctrl = pw.controller
            if ctrl is None:
                return
            library = ctrl.zones[Zone.LIBRARY]
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            # top(2) is bottom→top; look at them top-first.
            looked = list(reversed(library.top(2)))
            for card in looked:
                try:
                    to_bin = ctrl.choose_yes_no(
                        f"Surveil: put {getattr(card, 'name', 'card')} into your graveyard?"
                    )
                except Exception:
                    to_bin = False
                if to_bin and library.contains(card):
                    library.remove(card)
                    graveyard.add(card)
                # Otherwise it stays on top (order preserved).

        def _minus1(game: "GameState") -> None:
            """Any number of target players each discard a card."""
            from engine.game import discard

            for tp in _chosen_targets(pw):
                if tp not in game.players:
                    continue
                hand = tp.zones[Zone.HAND]
                cards = hand.get_all()
                if not cards:
                    continue
                try:
                    chosen = tp.choose_card(cards, "Discard a card")
                except Exception:
                    chosen = cards[-1]
                if chosen is None or not hand.contains(chosen):
                    chosen = cards[-1]
                discard(game, tp, chosen)

        def _minus2(game: "GameState") -> None:
            """Return target creature card (MV ≤ 3) from your graveyard."""
            from engine.zones import move_to_zone

            ctrl = pw.controller
            targets = _chosen_targets(pw)
            target = targets[0] if targets else None
            if ctrl is None or target is None:
                return
            graveyard = ctrl.zones[Zone.GRAVEYARD]
            if not graveyard.contains(target):
                return
            if CardType.CREATURE not in getattr(target, "card_types", set()):
                return
            cost = getattr(target, "mana_cost", None)
            if cost is not None and cost.cmc > 3:
                return
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        def _minus7(game: "GameState") -> None:
            """Flip five coins; target opponent skips X turns (X = heads)."""
            targets = _chosen_targets(pw)
            target = targets[0] if targets else None
            if target is None:
                return
            rng = getattr(game, "rng", None)
            if rng is None:
                import random

                rng = random.Random()
                game.rng = rng
            heads = sum(1 for _ in range(5) if rng.randint(0, 1) == 1)
            if heads > 0:
                target.skip_turns = getattr(target, "skip_turns", 0) + heads

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
                description="−2: Return target creature card (MV ≤ 3) from your graveyard.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description="−7: Flip five coins; target opponent skips their next X turns.",
            ),
        ]
