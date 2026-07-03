"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

_MANA_COST = ManaCost(generic=1, pips={ManaType.BLACK: 2})


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — starting loyalty 3.

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
        kwargs.setdefault("mana_cost", _MANA_COST)
        kwargs.setdefault("starting_loyalty", 3)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Ral"}
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
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

        # +1: Surveil 2
        def _plus1(g: "GameState") -> None:
            ctrl = pw.controller
            if ctrl is None:
                return
            library = g.get_library(ctrl)
            graveyard = g.get_graveyard(ctrl)

            # Peel top 2 from library.
            surveiled: list[Any] = []
            for _ in range(2):
                cards = library.get_all()
                if not cards:
                    break
                top = cards[-1]
                library.remove(top)
                surveiled.append(top)

            # For each, player chooses graveyard or top of library.
            kept: list[Any] = []
            for card in surveiled:
                try:
                    keep = ctrl.choose_yes_no(
                        f"Keep {getattr(card, 'name', 'card')} on top? (No = graveyard)"
                    )
                except Exception:
                    keep = True
                if keep:
                    kept.append(card)
                else:
                    graveyard.add(card)
            # Put kept cards back on top in surveiled order.
            for card in kept:
                library.add(card, position="top")

        # −1: Any number of target players each discard a card
        def _minus1(g: "GameState") -> None:
            from engine.game import discard
            targets = getattr(pw, "chosen_targets", [])
            for target_player in targets:
                hand = list(g.get_hand(target_player).get_all())
                if not hand:
                    continue
                try:
                    chosen = target_player.choose_card(hand, "Choose a card to discard")
                except Exception:
                    chosen = hand[0]
                if chosen is not None and g.get_hand(target_player).contains(chosen):
                    discard(g, target_player, chosen)

        # −2: Return target creature card with MV ≤ 3 from graveyard to battlefield
        def _minus2(g: "GameState") -> None:
            from engine.zones import move_to_zone
            ctrl = pw.controller
            if ctrl is None:
                return
            targets = getattr(pw, "chosen_targets", [])
            target_card = targets[0] if targets else None
            if target_card is None:
                return
            graveyard = g.get_graveyard(ctrl)
            if not graveyard.contains(target_card):
                return
            mc = getattr(target_card, "mana_cost", None)
            mv = mc.cmc if mc else 0
            if mv > 3:
                return
            target_card.controller = ctrl
            if target_card.owner is None:
                target_card.owner = ctrl
            move_to_zone(g, target_card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

        # −7: Flip five coins; target opponent skips next X turns (X = heads)
        def _minus7(g: "GameState") -> None:
            targets = getattr(pw, "chosen_targets", [])
            target_opp = targets[0] if targets else None
            if target_opp is None:
                return
            heads = sum(g.rng.randint(0, 1) for _ in range(5))
            if heads > 0:
                if not hasattr(target_opp, "skip_turns"):
                    target_opp.skip_turns = 0
                target_opp.skip_turns += heads

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
                description=(
                    "−2: Return target creature card with mana value 3 or less "
                    "from your graveyard to the battlefield."
                ),
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=_minus7,
                description=(
                    "−7: Flip five coins. Target opponent skips their next X turns."
                ),
            ),
        ]
